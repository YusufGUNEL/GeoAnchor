"""Can the system tell its own right answers from its wrong ones?

RoMa finds the correct alignment on 16% of night frames and hands back a
confident-looking answer on the other 84%. That is worse than useless to a
particle filter: a fix it cannot trust is a fix that will drag the estimate off
the map. Inlier count, which carries this job in daylight, appears to have
stopped working -- every frame clears the daylight threshold of 15.

(It had not. Running this script showed the count still separates right from
wrong at AUC 0.854, with a median of 2234 on correct fixes against 660 on wrong
ones. What broke at night was the threshold, not the signal. The four measures
below were written before that was known and are kept as they were, because the
comparison is the point: a purpose-built verification score barely beats a
recalibrated version of the signal that was there all along.)

So the question is not "can we match better" but "can we check". After an
alignment is proposed, the thermal patch can be warped into the satellite frame
and the two compared directly. If some measure of that overlap separates the
16% from the 84%, the night pipeline becomes possible: keep the good fixes,
throw the rest away, and coast on odometry in between -- exactly what GeoAnchor
already does through the frames daylight matching cannot handle.

Four candidate measures, all modality-aware, none of them trained:

  ncc_dog       correlation of band-passed images -- appearance removed,
                structure kept
  mi            mutual information, the classical multimodal registration score:
                it asks whether one image predicts the other, not whether they
                look alike
  yon_uyumu     gradient orientation agreement, measured as cos(2*delta) so that
                an edge which is bright-to-dark in one modality and dark-to-
                bright in the other still counts as agreement
  ic_nokta      the daylight signal, included as the control -- and it is the
                one that survives recalibration best

Reported as AUC: the probability that a correct fix scores above a wrong one.
0.5 is a coin flip and means the measure is worthless.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.matching import estimate_similarity  # noqa: E402

sys.path.insert(0, str(ROOT / "night"))
from importlib import import_module  # noqa: E402

kopru = import_module("02_kopru")

DATA = ROOT / "night" / "veri" / "thermal_dataset"
OUT = ROOT / "night" / "sonuclar"
OFFSET = kopru.OFFSET
N_PAIRS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
TOL_PX = 20.0


def warp_pair(thermal: np.ndarray, satellite: np.ndarray, M: np.ndarray):
    """Put the thermal patch into the satellite frame; return both plus the mask."""
    h, w = satellite.shape[:2]
    warped = cv2.warpAffine(thermal, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    valid = cv2.warpAffine(np.ones_like(thermal, dtype=np.uint8), M, (w, h),
                           flags=cv2.INTER_NEAREST, borderValue=0).astype(bool)
    # Ignore the frame edges: interpolation there is half background.
    valid = cv2.erode(valid.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    return warped, satellite, valid


def ncc(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    x = a[mask].astype(np.float64)
    y = b[mask].astype(np.float64)
    if x.size < 500 or x.std() < 1e-6 or y.std() < 1e-6:
        return 0.0
    return float(np.mean((x - x.mean()) * (y - y.mean()) / (x.std() * y.std())))


def mutual_information(a: np.ndarray, b: np.ndarray, mask: np.ndarray, bins: int = 32) -> float:
    x = a[mask].astype(np.float32)
    y = b[mask].astype(np.float32)
    if x.size < 500:
        return 0.0
    hist, _, _ = np.histogram2d(x, y, bins=bins, range=[[0, 256], [0, 256]])
    p = hist / hist.sum()
    px = p.sum(axis=1, keepdims=True)
    py = p.sum(axis=0, keepdims=True)
    nz = p > 0
    return float(np.sum(p[nz] * np.log(p[nz] / (px @ py)[nz])))


def orientation_agreement(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """cos(2*delta) weighted by gradient strength.

    Doubling the angle folds a 180 degree flip onto itself, so an edge that
    reverses contrast between modalities -- which is most of them -- still
    registers as agreement rather than as opposition.
    """
    def grad(img):
        img = cv2.GaussianBlur(img, (0, 0), 1.5)
        gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3)
        return np.arctan2(gy, gx), cv2.magnitude(gx, gy)

    ta, ma = grad(a)
    tb, mb = grad(b)
    w = (ma * mb)[mask]
    if w.sum() < 1e-6:
        return 0.0
    d = (ta - tb)[mask]
    return float(np.sum(w * np.cos(2 * d)) / w.sum())


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank-based AUC. No sklearn, no dependency."""
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order), dtype=float)
    ranks[order] = np.arange(1, len(order) + 1)
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from src.matching import RomaMatcher

    with h5py.File(DATA / "test_database.h5", "r") as sat, \
         h5py.File(DATA / "test_queries.h5", "r") as thr:
        pairs = kopru.build_pairs(kopru.coords(sat), N_PAIRS)
        thr_imgs = [kopru.gray(thr["image_data"][i]) for i, _ in pairs]
        sat_imgs = [kopru.gray(sat["image_data"][j]) for _, j in pairs]
    print(f"{len(pairs)} cift, gercek kayma {OFFSET} px\n", flush=True)

    matcher = RomaMatcher(device="cuda")
    rep = kopru.REPS["clahe+dog"]          # the best arm from 02
    rows = []
    for k, (t_raw, s_raw) in enumerate(zip(thr_imgs, sat_imgs)):
        t_rep, s_rep = rep(t_raw, True), rep(s_raw, False)
        pa, pb, _ = matcher.match(t_rep, s_rep)
        M, _, n = estimate_similarity(pa, pb)
        if M is None:
            continue
        err = float(np.hypot(M[0, 2] + OFFSET, M[1, 2]))
        warped, target, valid = warp_pair(t_rep, s_rep, M)
        rows.append({
            "hata_px": err,
            "dogru": err < TOL_PX,
            "ic_nokta": float(n),
            "ncc_dog": ncc(warped, target, valid),
            "mi": mutual_information(warped, target, valid),
            "yon_uyumu": orientation_agreement(warped, target, valid),
        })
        print(f"\r  {k + 1}/{len(pairs)}  hata {err:7.1f} px", end="", flush=True)
    print()

    labels = np.array([r["dogru"] for r in rows])
    print(f"\ndogru fix: {labels.sum()}/{len(labels)} = %{100 * labels.mean():.0f}\n")
    print("=" * 58)
    print(f"{'olcut':16s} {'AUC':>8s}   {'dogru ort':>10s} {'yanlis ort':>11s}")
    print("-" * 58)
    summary = {}
    for key in ("ic_nokta", "ncc_dog", "mi", "yon_uyumu"):
        s = np.array([r[key] for r in rows])
        a = auc(s, labels)
        summary[key] = {"auc": a, "dogru_ort": float(s[labels].mean()),
                        "yanlis_ort": float(s[~labels].mean())}
        print(f"{key:16s} {a:8.3f}   {s[labels].mean():10.3f} {s[~labels].mean():11.3f}")
    print("=" * 58)
    print("AUC 0.5 = yazi tura, 1.0 = kusursuz ayirma")

    (OUT / f"03_dogrulama_{len(rows)}.json").write_text(
        json.dumps({"ozet": summary, "kareler": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\n-> {OUT / f'03_dogrulama_{len(rows)}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Can a cheap representation close the thermal-to-satellite gap?

The baseline says LoFTR sees nothing at night. Looking at a pair explains why:
the two images do not share brightness at all -- sand is bright in optical and
flat in thermal, vegetation is dark in thermal and green in optical -- but they
do share *structure*: roads, field boundaries, building outlines survive in both.

So before training anything, the honest first question is whether throwing away
appearance and keeping structure is enough. Each representation below is a few
lines of OpenCV, costs nothing, and is applied identically to both sides. If one
of them works, the night problem was a preprocessing problem. If none does, we
have earned the right to train something, and we know exactly why.

Run with LoFTR because it is fast and because it scores zero on raw input --
any movement off zero is unambiguous.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.matching import estimate_similarity  # noqa: E402

DATA = ROOT / "night" / "veri" / "thermal_dataset"
OUT = ROOT / "night" / "sonuclar"
OFFSET = 70
N_PAIRS = 50
MIN_INLIERS = 15


def _u8(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    lo, hi = np.percentile(x, 1), np.percentile(x, 99)
    if hi - lo < 1e-6:
        return np.zeros_like(x, dtype=np.uint8)
    return np.clip((x - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)


def rep_ham(g: np.ndarray, thermal: bool) -> np.ndarray:
    return g


def rep_clahe(g: np.ndarray, thermal: bool) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)


def rep_sobel(g: np.ndarray, thermal: bool) -> np.ndarray:
    """Gradient magnitude: keeps where things change, discards what colour they are."""
    g = cv2.GaussianBlur(g, (0, 0), 1.2)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return _u8(cv2.magnitude(gx, gy))


def rep_dog(g: np.ndarray, thermal: bool) -> np.ndarray:
    """Difference of Gaussians: a band-pass that removes slow brightness trends.

    Most of what separates the two modalities is low frequency -- the overall
    warmth of sand versus its colour. Structure lives higher up.
    """
    a = cv2.GaussianBlur(g.astype(np.float32), (0, 0), 1.0)
    b = cv2.GaussianBlur(g.astype(np.float32), (0, 0), 4.0)
    return _u8(a - b)


def rep_canny(g: np.ndarray, thermal: bool) -> np.ndarray:
    e = cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.2), 40, 120)
    return cv2.GaussianBlur(e, (0, 0), 1.0)


def rep_ters_clahe(g: np.ndarray, thermal: bool) -> np.ndarray:
    """Thermal polarity is not optical polarity -- vegetation is cold and dark
    in one, bright green in the other. Flip one side and see if that alone helps."""
    g = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)
    return 255 - g if thermal else g


def rep_dog_clahe(g: np.ndarray, thermal: bool) -> np.ndarray:
    return rep_dog(cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g), thermal)


REPS = {
    "ham": rep_ham,
    "clahe": rep_clahe,
    "sobel": rep_sobel,
    "dog": rep_dog,
    "canny": rep_canny,
    "ters+clahe": rep_ters_clahe,
    "clahe+dog": rep_dog_clahe,
}


def gray(a: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) if a.ndim == 3 else a


def coords(f: h5py.File) -> np.ndarray:
    names = [n.decode() if isinstance(n, bytes) else n for n in f["image_name"][:]]
    return np.array([[int(p) for p in n.strip("@").split("@")] for n in names])


def build_pairs(xy: np.ndarray, n: int) -> list[tuple[int, int]]:
    lookup = {(int(a), int(b)): i for i, (a, b) in enumerate(xy)}
    pairs = [(i, lookup[(int(a), int(b) + OFFSET)])
             for i, (a, b) in enumerate(xy) if (int(a), int(b) + OFFSET) in lookup]
    stride = max(1, len(pairs) // n)
    return pairs[::stride][:n]


def evaluate(rep_name: str, rep, matcher, thr_imgs, sat_imgs) -> dict:
    errs, inliers, t0 = [], [], time.time()
    for k, (a_raw, b_raw) in enumerate(zip(thr_imgs, sat_imgs)):
        a = rep(a_raw, True)
        b = rep(b_raw, False)
        pa, pb, _ = matcher.match(a, b)
        M, _, n = estimate_similarity(pa, pb)
        inliers.append(n)
        if M is not None and n >= MIN_INLIERS:
            errs.append(float(np.hypot(M[0, 2] + OFFSET, M[1, 2])))
        print(f"\r  {rep_name}: {k + 1}/{len(thr_imgs)}  ic nokta {n}   ", end="", flush=True)
    print()
    good = [e for e in errs if e < 20]
    accepted = sum(1 for n in inliers if n >= MIN_INLIERS)
    # Precision is the number that decides whether a fix can be trusted: of the
    # frames the system chose to accept, how many were actually right. A filter
    # survives a low acceptance rate by coasting on odometry -- GeoAnchor already
    # does that through 23% of daylight frames. It cannot survive being lied to.
    return {
        "temsil": rep_name,
        "dogru_konum_orani": len(good) / len(thr_imgs),
        "kesinlik": len(good) / accepted if accepted else None,
        "medyan_ic_nokta": float(np.median(inliers)),
        "kabul_orani": accepted / len(inliers),
        "medyan_hata_px": float(np.median(errs)) if errs else None,
        "sn_kare": round((time.time() - t0) / len(thr_imgs), 2),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from src.matching import LoFTRMatcher

    with h5py.File(DATA / "test_database.h5", "r") as sat, \
         h5py.File(DATA / "test_queries.h5", "r") as thr:
        pairs = build_pairs(coords(sat), N_PAIRS)
        # Read once; every representation then works on the same pixels, so a
        # difference between rows cannot be a difference in sampling.
        thr_imgs = [gray(thr["image_data"][i]) for i, _ in pairs]
        sat_imgs = [gray(sat["image_data"][j]) for _, j in pairs]
    print(f"{len(pairs)} termal/uydu cifti, gercek kayma {OFFSET} px\n", flush=True)

    which = sys.argv[1] if len(sys.argv) > 1 else "loftr"
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else list(REPS)
    if which == "roma":
        from src.matching import RomaMatcher
        matcher = RomaMatcher(device="cuda")
    else:
        matcher = LoFTRMatcher(device="cuda")
    print(f"eslestirici: {which}\n", flush=True)
    rows = [evaluate(n, REPS[n], matcher, thr_imgs, sat_imgs) for n in only]
    rows.sort(key=lambda r: -r["dogru_konum_orani"])

    print("\n" + "=" * 72)
    print(f"{'temsil':16s} {'KONUM DOGRU':>13s} {'kesinlik':>10s} {'kabul':>8s} "
          f"{'ic nokta':>10s} {'medyan hata':>13s}")
    print("-" * 72)
    for r in rows:
        err = f"{r['medyan_hata_px']:.1f} px" if r["medyan_hata_px"] is not None else "-"
        kes = f"{r['kesinlik'] * 100:.0f}%" if r["kesinlik"] is not None else "-"
        print(f"{r['temsil']:16s} {r['dogru_konum_orani'] * 100:12.0f}% {kes:>10s} "
              f"{r['kabul_orani'] * 100:7.0f}% {r['medyan_ic_nokta']:10.0f} {err:>13s}")
    print("=" * 72)

    (OUT / f"02_kopru_{which}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(f"\n-> {OUT / f'02_kopru_{which}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

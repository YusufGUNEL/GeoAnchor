"""Turning two weak signals into a gate the filter can actually rely on.

Verification found two measures that separate a correct night fix from a wrong
one: gradient-orientation agreement (AUC 0.885) and, once its daylight threshold
is thrown away, the inlier count (AUC 0.854). Neither is a decision on its own.
A decision needs an operating point, and the operating point is not chosen by
maximising accuracy -- it is chosen by what a particle filter can survive.

The filter can survive silence. GeoAnchor already flies through stretches where
matching gives it nothing, coasting on odometry, and re-anchors afterwards. What
it cannot survive is a confident wrong fix, which pulls the whole particle cloud
somewhere it has never been. So the gate is tuned for precision and recall is
whatever precision leaves behind.

Reads the per-frame records written by 03_dogrulama.py; runs in a second and
needs no GPU.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "night" / "sonuclar"
TARGET_PRECISION = 0.90


def kayit_dosyasi() -> Path:
    """The run to read: an explicit argument, else the largest one on disk.

    03_dogrulama.py names its output after the number of frames it got through,
    so picking the biggest file means the gate is always fitted on the most
    evidence available rather than on whichever run happened to finish last.
    """
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    # The frame count is the LAST number in the stem: the leading "03" is the
    # script number and is the same for every run, so keying on the first match
    # ranks every file equally and returns whichever the glob happened to list.
    runs = sorted(OUT.glob("03_dogrulama_*.json"),
                  key=lambda f: int(re.findall(r"(\d+)", f.stem)[-1]))
    if not runs:
        raise SystemExit("03_dogrulama_*.json yok -- once night/03_dogrulama.py calistir")
    return runs[-1]


def curve(score: np.ndarray, labels: np.ndarray, higher_is_better: bool = True):
    """Precision and recall at every threshold the data actually contains."""
    s = score if higher_is_better else -score
    order = np.argsort(-s)
    lab = labels[order]
    tp = np.cumsum(lab)
    kept = np.arange(1, len(lab) + 1)
    precision = tp / kept
    recall = tp / max(labels.sum(), 1)
    return precision, recall, s[order]


def best_at_precision(score, labels, higher_is_better=True, target=TARGET_PRECISION):
    p, r, thr = curve(score, labels, higher_is_better)
    ok = np.where(p >= target)[0]
    if len(ok) == 0:
        return None
    i = ok[np.argmax(r[ok])]
    return {"kesinlik": float(p[i]), "duyarlilik": float(r[i]),
            "esik": float(thr[i] if higher_is_better else -thr[i]),
            "kabul_edilen": int(i + 1)}


def held_out(score, labels, higher_is_better=True, target=TARGET_PRECISION,
             repeats=400, seed=0):
    """Fit the threshold on half the frames, report what it does on the other half.

    The number best_at_precision returns is measured on the frames that chose
    the threshold, so it is an upper bound on what the gate will do in flight:
    with few correct fixes, some threshold always looks perfect in hindsight.
    Splitting separates the two, and repeating over random splits keeps one
    lucky partition from standing in for the answer. The median over repeats is
    reported, with the 10th percentile as the pessimistic end.
    """
    rng = np.random.default_rng(seed)
    idx = np.arange(len(labels))
    precisions, recalls, thresholds = [], [], []
    for _ in range(repeats):
        rng.shuffle(idx)
        fit, test = idx[: len(idx) // 2], idx[len(idx) // 2:]
        if labels[fit].sum() == 0 or labels[test].sum() == 0:
            continue
        got = best_at_precision(score[fit], labels[fit], higher_is_better, target)
        if got is None:
            continue
        t = got["esik"]
        keep = score[test] >= t if higher_is_better else score[test] <= t
        if keep.sum() == 0:
            precisions.append(float("nan"))
            recalls.append(0.0)
            thresholds.append(t)
            continue
        precisions.append(float(labels[test][keep].mean()))
        recalls.append(float(labels[test][keep].sum() / labels[test].sum()))
        thresholds.append(t)
    if not precisions:
        return None
    p = np.array(precisions, dtype=float)
    r = np.array(recalls, dtype=float)
    valid = ~np.isnan(p)
    return {
        "bolme": len(precisions),
        "sessiz_bolme": int((~valid).sum()),   # splits where the gate accepted nothing
        "kesinlik_medyan": float(np.median(p[valid])) if valid.any() else float("nan"),
        "kesinlik_p10": float(np.percentile(p[valid], 10)) if valid.any() else float("nan"),
        "duyarlilik_medyan": float(np.median(r)),
        "esik_medyan": float(np.median(thresholds)),
    }


def main() -> int:
    kayit = kayit_dosyasi()
    print(f"kayit: {kayit.name}")
    data = json.loads(kayit.read_text(encoding="utf-8"))
    rows = data["kareler"]
    labels = np.array([r["dogru"] for r in rows])
    print(f"{len(rows)} kare, {labels.sum()} tanesi dogru (%{100 * labels.mean():.0f})\n")

    singles = {
        "yon_uyumu": (np.array([r["yon_uyumu"] for r in rows]), True),
        "ic_nokta": (np.array([r["ic_nokta"] for r in rows]), True),
        "-ncc_dog": (-np.array([r["ncc_dog"] for r in rows]), True),
    }

    # Two signals, different failure modes: orientation agreement is about the
    # structure lining up, inlier count is about the matcher having anything to
    # say at all. A frame has to clear both, which is why the product works
    # better than either -- and it needs no fitting, so it cannot overfit a
    # small run.
    yon = singles["yon_uyumu"][0]
    ic = singles["ic_nokta"][0]
    combo = (yon - yon.min()) / (np.ptp(yon) + 1e-9) * (ic / (ic.max() + 1e-9))
    singles["yon x ic_nokta"] = (combo, True)

    print("=" * 78)
    print(f"{'olcut':18s} {'ornek-ici':>22s} {'AYRIK KUMEDE':>30s}")
    print(f"{'':18s} {'kesinlik':>10s} {'duyar.':>11s} {'kesinlik (p10)':>18s} {'duyar.':>11s}")
    print("-" * 78)
    best = {}
    for name, (score, hib) in singles.items():
        got = best_at_precision(score, labels, hib)
        out = held_out(score, labels, hib)
        best[name] = {"ornek_ici": got, "ayrik": out}
        if got is None:
            print(f"{name:18s} {'%90 kesinlige ulasilamiyor':>22s}")
            continue
        tail = "-" if out is None else (
            f"{out['kesinlik_medyan'] * 100:11.0f}% "
            f"({out['kesinlik_p10'] * 100:3.0f}%) {out['duyarlilik_medyan'] * 100:10.0f}%")
        print(f"{name:18s} {got['kesinlik'] * 100:9.0f}% {got['duyarlilik'] * 100:10.0f}%"
              f" {tail}")
    print("=" * 78)
    print("ornek-ici sayilar esigi SECEN karelerde olculuyor -- iyimser.")
    print("ayrik kume: esik karelerin yarisinda seciliyor, diger yarisinda olculuyor,")
    print("400 rastgele bolme, medyan (ve karamsar uc icin %10'luk dilim).")

    # Ranked by held-out recall, but only among measures that still hold the
    # precision target off the frames that chose their threshold. Ranking by
    # recall alone picks whichever measure overfits hardest -- on the 120-frame
    # run that was -ncc_dog, best recall and the worst precision of the three.
    qualified = [k for k, v in best.items()
                 if v["ayrik"] and v["ayrik"]["kesinlik_medyan"] >= TARGET_PRECISION]
    if not qualified:
        print(f"\nhicbir olcut ayrik kumede %{TARGET_PRECISION * 100:.0f} kesinligi "
              "tutturamiyor -- kapi bu veriyle kurulamaz.")
    winner = max(qualified, key=lambda k: best[k]["ayrik"]["duyarlilik_medyan"],
                 default=None)
    if winner:
        w, a = best[winner]["ornek_ici"], best[winner]["ayrik"]
        print(f"\nen iyi kapi: {winner}")
        print(f"  ayrik kumede kesinlik   %{a['kesinlik_medyan'] * 100:.0f}  "
              f"(karamsar uc %{a['kesinlik_p10'] * 100:.0f})")
        print(f"  ayrik kumede duyarlilik %{a['duyarlilik_medyan'] * 100:.0f}")
        print(f"  esik {a['esik_medyan']:.1f}; ornek-ici {w['kabul_edilen']}/{len(rows)} "
              "kare kabul, gerisi sessizce atiliyor")
        if a["sessiz_bolme"]:
            print(f"  {a['sessiz_bolme']}/{a['bolme']} bolmede kapi hicbir kareyi "
                  "kabul etmedi -- suskunluk da bir sonuc")
        print(f"\nKarsilastirma: kapisiz RoMa %{100 * labels.mean():.0f} kesinlikle "
              "her kareyi kabul ediyordu.")

    (OUT / "04_kapi.json").write_text(json.dumps(
        {"kayit": kayit.name, "n": len(rows), "dogru": int(labels.sum()),
         "hedef_kesinlik": TARGET_PRECISION, "olcutler": best},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT / '04_kapi.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

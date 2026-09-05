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
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "night" / "sonuclar"
TARGET_PRECISION = 0.90


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


def main() -> int:
    data = json.loads((OUT / "03_dogrulama.json").read_text(encoding="utf-8"))
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
    # better than either -- and it needs no fitting, so it cannot overfit 120
    # frames.
    yon = singles["yon_uyumu"][0]
    ic = singles["ic_nokta"][0]
    combo = (yon - yon.min()) / (np.ptp(yon) + 1e-9) * (ic / (ic.max() + 1e-9))
    singles["yon x ic_nokta"] = (combo, True)

    print("=" * 72)
    print(f"{'olcut':18s} {'%90 kesinlikte duyarlilik':>26s} {'esik':>12s}")
    print("-" * 72)
    best = {}
    for name, (score, hib) in singles.items():
        got = best_at_precision(score, labels, hib)
        best[name] = got
        if got is None:
            print(f"{name:18s} {'%90 kesinlige ulasilamiyor':>26s}")
        else:
            print(f"{name:18s} {got['duyarlilik'] * 100:25.0f}% {got['esik']:12.1f}")
    print("=" * 72)

    winner = max((k for k, v in best.items() if v), key=lambda k: best[k]["duyarlilik"],
                 default=None)
    if winner:
        w = best[winner]
        print(f"\nen iyi kapi: {winner}")
        print(f"  kesinlik   %{w['kesinlik'] * 100:.0f}  -- kabul edilen fix'lerin bu kadari dogru")
        print(f"  duyarlilik %{w['duyarlilik'] * 100:.0f}  -- dogru fix'lerin bu kadari yakalaniyor")
        print(f"  {w['kabul_edilen']}/{len(rows)} kare kabul ediliyor, gerisi sessizce atiliyor")
        print("\nKarsilastirma: kapisiz RoMa %9 kesinlikle her kareyi kabul ediyordu.")

    (OUT / "04_kapi.json").write_text(json.dumps(best, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(f"\n-> {OUT / '04_kapi.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

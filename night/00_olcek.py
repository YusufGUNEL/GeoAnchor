"""What does one grid unit mean in pixels, and what can the matcher do at best?

The dataset names its patches `@x@y` and never says what x and y are counted in.
Guessing would put a silent scale factor under every error we report later, so
this measures it instead: take two satellite patches whose grid coordinates
differ by a known amount, match them to each other, and read off how far the
image actually shifted.

Both images here are satellite, so this is the same-modality case -- the ceiling.
Whatever the matcher scores in this script is the best it could possibly do on
the thermal-to-satellite problem, and the gap between the two numbers is exactly
what the night project has to close.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.matching import LoFTRMatcher, estimate_similarity  # noqa: E402

DATA = ROOT / "night" / "veri" / "thermal_dataset"
STEP = 35          # the grid step the coordinates move in
N_PAIRS = 60


def coords(f: h5py.File) -> np.ndarray:
    names = [n.decode() if isinstance(n, bytes) else n for n in f["image_name"][:]]
    return np.array([[int(p) for p in n.strip("@").split("@")] for n in names])


def gray(a: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) if a.ndim == 3 else a


def main() -> int:
    with h5py.File(DATA / "test_database.h5", "r") as f:
        xy = coords(f)
        lookup = {(int(x), int(y)): i for i, (x, y) in enumerate(xy)}

        # neighbours one grid step apart in y, spread across the whole map so a
        # single easy region cannot carry the result
        pairs = []
        for i, (x, y) in enumerate(xy):
            j = lookup.get((int(x), int(y) + STEP))
            if j is not None:
                pairs.append((i, j))
        stride = max(1, len(pairs) // N_PAIRS)
        pairs = pairs[::stride][:N_PAIRS]
        print(f"{len(pairs)} komsu cift, grid adimi {STEP} birim", flush=True)

        matcher = LoFTRMatcher(device="cuda")
        shifts, inliers, ok = [], [], 0
        for k, (i, j) in enumerate(pairs):
            a = gray(f["image_data"][i])
            b = gray(f["image_data"][j])
            pa, pb, _ = matcher.match(a, b)
            M, _, n = estimate_similarity(pa, pb)
            inliers.append(n)
            if M is not None and n >= 15:
                ok += 1
                shifts.append((float(M[0, 2]), float(M[1, 2])))
            print(f"\r  {k + 1}/{len(pairs)}  ic nokta {n}", end="", flush=True)
        print()

    inliers = np.array(inliers)
    print(f"\ntutma orani (>=15 ic nokta): {ok}/{len(pairs)} = %{100 * ok / len(pairs):.0f}")
    print(f"ic nokta: medyan {np.median(inliers):.0f}, min {inliers.min()}, maks {inliers.max()}")

    if not shifts:
        print("hicbir cift tutmadi, olcek olculemedi")
        return 1

    s = np.array(shifts)
    dy = np.median(np.abs(s[:, 1]))
    dx = np.median(np.abs(s[:, 0]))
    print(f"\nolculen kayma: dx {dx:.1f} px, dy {dy:.1f} px  ({STEP} birimlik grid adimi icin)")
    print(f"-> 1 grid birimi = {dy / STEP:.3f} piksel")
    print(f"-> 512 px'lik bir kare {512 * STEP / dy:.0f} grid birimi kapsiyor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

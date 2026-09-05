"""The baseline: what the daytime system does when the camera goes thermal.

No improvement is claimed here and none is attempted. The point is to put a
number on the gap before touching it, because "we improved thermal matching" is
worth nothing without the sentence that comes before it.

Three arms, same matcher, same patches, same measurement:

  satellite -> satellite   the ceiling. Same sensor, same season. Whatever this
                           scores is the best the pipeline could do.
  thermal   -> satellite   the actual night problem, with LoFTR, which is what
                           GeoAnchor uses by default.
  thermal   -> satellite   the same problem with RoMa, which the daytime work
                           already showed rescues the hard flights.

Pairs are deliberately offset by a known number of pixels rather than perfectly
aligned. A zero-offset test flatters any matcher that quietly returns the
identity when it has nothing: here, returning identity scores as a full miss.
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
OFFSET = 70          # pixels of true displacement between the two patches
N_PAIRS = 100
MIN_INLIERS = 15


def gray(a: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY) if a.ndim == 3 else a


def coords(f: h5py.File) -> np.ndarray:
    names = [n.decode() if isinstance(n, bytes) else n for n in f["image_name"][:]]
    return np.array([[int(p) for p in n.strip("@").split("@")] for n in names])


def build_pairs(xy: np.ndarray, n: int) -> list[tuple[int, int]]:
    """Index pairs whose true displacement is exactly OFFSET pixels.

    The second grid coordinate was measured to move the image horizontally by
    one pixel per unit (night/00_olcek.py), so a coordinate step of OFFSET is a
    displacement of OFFSET pixels in x.
    """
    lookup = {(int(a), int(b)): i for i, (a, b) in enumerate(xy)}
    pairs = [(i, lookup[(int(a), int(b) + OFFSET)])
             for i, (a, b) in enumerate(xy) if (int(a), int(b) + OFFSET) in lookup]
    stride = max(1, len(pairs) // n)
    return pairs[::stride][:n]


def run(name: str, matcher, src_file: h5py.File, dst_file: h5py.File,
        pairs: list[tuple[int, int]]) -> dict:
    errs, inliers, hits, t0 = [], [], 0, time.time()
    for k, (i, j) in enumerate(pairs):
        a = gray(src_file["image_data"][i])
        b = gray(dst_file["image_data"][j])
        pa, pb, _ = matcher.match(a, b)
        M, _, n = estimate_similarity(pa, pb)
        inliers.append(n)
        if M is not None and n >= MIN_INLIERS:
            hits += 1
            # truth: b sits OFFSET pixels along x from a, so a point in a maps
            # to the same point minus OFFSET in b.
            errs.append(float(np.hypot(M[0, 2] + OFFSET, M[1, 2])))
        print(f"\r  {name}: {k + 1}/{len(pairs)}  ic nokta {n}", end="", flush=True)
    print()

    inliers = np.array(inliers)
    good = [e for e in errs if e < 20]        # within 20 px of the true offset
    # `tutma_orani` counts frames that produced enough inliers to be *accepted*.
    # For a dense matcher that is not evidence of anything -- RoMa clears the
    # threshold on every frame and is still wrong 98% of the time. The column
    # that means something is `dogru_konum_orani`, kept separate for that reason.
    return {
        "kol": name,
        "cift": len(pairs),
        "tutma_orani": hits / len(pairs),
        "medyan_ic_nokta": float(np.median(inliers)),
        "ic_nokta_p10": float(np.percentile(inliers, 10)),
        "dogru_konum_orani": len(good) / len(pairs),
        "medyan_hata_px": float(np.median(errs)) if errs else None,
        "sn_kare": round((time.time() - t0) / len(pairs), 2),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from src.matching import LoFTRMatcher

    with h5py.File(DATA / "test_database.h5", "r") as sat, \
         h5py.File(DATA / "test_queries.h5", "r") as thr:
        pairs = build_pairs(coords(sat), N_PAIRS)
        print(f"{len(pairs)} cift, gercek kayma {OFFSET} px\n", flush=True)

        rows = []
        loftr = LoFTRMatcher(device="cuda")
        rows.append(run("uydu->uydu  (tavan, LoFTR)", loftr, sat, sat, pairs))
        rows.append(run("termal->uydu (LoFTR)", loftr, thr, sat, pairs))
        del loftr

        try:
            from src.matching import RomaMatcher
            roma = RomaMatcher(device="cuda")
            rows.append(run("termal->uydu (RoMa)", roma, thr, sat, pairs))
        except Exception as exc:
            print(f"RoMa atlandi: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 78)
    print(f"{'kol':30s} {'kabul':>8s} {'ic nokta':>10s} {'KONUM DOGRU':>13s} {'medyan hata':>13s}")
    print("-" * 78)
    for r in rows:
        err = f"{r['medyan_hata_px']:.1f} px" if r["medyan_hata_px"] is not None else "-"
        print(f"{r['kol']:30s} {r['tutma_orani'] * 100:7.0f}% {r['medyan_ic_nokta']:10.0f} "
              f"{r['dogru_konum_orani'] * 100:12.0f}% {err:>13s}")
    print("=" * 78)

    (OUT / "01_taban.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(f"\n-> {OUT / '01_taban.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

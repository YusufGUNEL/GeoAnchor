"""Do the representations succeed on the same frames, or on different ones?

02 measured each representation on its own and reported one number per arm:
sobel 12%, dog 12%, clahe+dog 16% of frames correctly located. Those numbers
are compatible with two completely different worlds, and only one of them is
worth working in:

  - the same easy frames succeed under every representation, in which case
    16% is close to the ceiling for this family of methods and the next move
    has to be a trained cross-modal matcher;
  - each representation succeeds somewhere else, in which case the union is
    much larger than 16% and the remaining problem is not finding the fix but
    knowing which one to keep.

02 could not tell these apart because it stored aggregates. This script keeps
the per-frame record, which also buys a second measurement for free: when two
representations independently propose the *same* transform, is the answer
right? Agreement between decorrelated methods is the classic cheap confidence
signal, and it needs no training and no threshold tuned on a handful of
frames -- which is exactly the weakness of the gate 04 currently fits.

Reports, on the same frames:

  per representation    correct rate, reproducing 02 as a sanity check
  union                 fraction where at least one representation is right
                        (the ceiling any selection rule could reach)
  agreement             of the frames where two representations land within
                        AGREE_PX of each other, how many are actually correct
                        -- precision and recall of agreement used as a gate

Cost is one RoMa pass per representation per frame, about 2.3 s each on a
3050 Ti, so the default 150 frames over three representations is roughly
17 minutes.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from itertools import combinations
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "night"))
sys.stdout.reconfigure(encoding="utf-8")

from src.matching import estimate_similarity  # noqa: E402

kopru = import_module("02_kopru")

DATA = ROOT / "night" / "veri" / "thermal_dataset"
OUT = ROOT / "night" / "sonuclar"
OFFSET = kopru.OFFSET
TOL_PX = 20.0
AGREE_PX = 20.0
N_PAIRS = int(sys.argv[1]) if len(sys.argv) > 1 else 150
# The three that scored above zero with RoMa in 02. "ham" is left out: at 2%
# it contributes nothing to a union and would cost a third of the runtime.
# A second argument narrows the list -- confirming one agreeing pair at 1000
# frames costs two RoMa passes rather than three, and by then the ceiling
# question the third arm answers is already settled.
REPS = (sys.argv[2].split(",") if len(sys.argv) > 2
        else ["clahe+dog", "dog", "sobel"])
if bad := [r for r in REPS if r not in kopru.REPS]:
    raise SystemExit(f"bilinmeyen temsil: {bad}; secenekler: {list(kopru.REPS)}")
if len(REPS) < 2:
    raise SystemExit("uzlasma icin en az iki temsil gerekiyor")


def evaluate(matcher, rep, thermal, satellite) -> dict:
    a, b = rep(thermal, True), rep(satellite, False)
    pa, pb, _ = matcher.match(a, b)
    M, _, n = estimate_similarity(pa, pb)
    if M is None:
        return {"var": False}
    dx, dy = float(M[0, 2]), float(M[1, 2])
    err = float(np.hypot(dx + OFFSET, dy))
    return {"var": True, "dx": dx, "dy": dy, "ic_nokta": float(n),
            "hata_px": err, "dogru": err < TOL_PX}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from src.matching import RomaMatcher

    with h5py.File(DATA / "test_database.h5", "r") as sat, \
         h5py.File(DATA / "test_queries.h5", "r") as thr:
        pairs = kopru.build_pairs(kopru.coords(sat), N_PAIRS)
        thr_imgs = [kopru.gray(thr["image_data"][i]) for i, _ in pairs]
        sat_imgs = [kopru.gray(sat["image_data"][j]) for _, j in pairs]
    print(f"{len(pairs)} cift x {len(REPS)} temsil, gercek kayma {OFFSET} px\n",
          flush=True)

    matcher = RomaMatcher(device="cuda")
    rows = []
    for k, (t, s) in enumerate(zip(thr_imgs, sat_imgs)):
        row = {name: evaluate(matcher, kopru.REPS[name], t, s) for name in REPS}
        rows.append(row)
        hits = "".join("+" if row[n].get("dogru") else "." for n in REPS)
        print(f"\r  {k + 1}/{len(pairs)}  [{hits}]", end="", flush=True)
    print("\n")

    n = len(rows)
    correct = {name: np.array([r[name].get("dogru", False) for r in rows])
               for name in REPS}
    union = np.any(np.stack([correct[name] for name in REPS]), axis=0)
    every = np.all(np.stack([correct[name] for name in REPS]), axis=0)

    print("=" * 62)
    print(f"{'temsil':14s} {'dogru':>8s}   {'sadece bu temsil':>18s}")
    print("-" * 62)
    only = {}
    for name in REPS:
        others = np.any(np.stack([correct[o] for o in REPS if o != name]), axis=0)
        only[name] = int((correct[name] & ~others).sum())
        print(f"{name:14s} {correct[name].mean() * 100:7.0f}% {only[name]:18d}")
    print("-" * 62)
    print(f"{'BIRLESIM':14s} {union.mean() * 100:7.0f}%   "
          f"(en iyi tek temsil %{max(c.mean() for c in correct.values()) * 100:.0f})")
    print(f"{'KESISIM':14s} {every.mean() * 100:7.0f}%")
    print("=" * 62)

    # Agreement as a gate: two representations proposing the same translation
    # is evidence independent of how many inliers either of them found.
    print(f"\nuzlasma kapisi (iki temsil {AGREE_PX:.0f} px icinde ayni yeri "
          "gosteriyorsa kabul)\n")
    print(f"{'cift':26s} {'kabul':>7s} {'kesinlik':>9s} {'duyarlilik':>11s}")
    print("-" * 62)
    agree_stats = {}
    for a, b in combinations(REPS, 2):
        ok = np.zeros(n, bool)
        right = np.zeros(n, bool)
        for i, row in enumerate(rows):
            ra, rb = row[a], row[b]
            if not (ra.get("var") and rb.get("var")):
                continue
            if np.hypot(ra["dx"] - rb["dx"], ra["dy"] - rb["dy"]) >= AGREE_PX:
                continue
            ok[i] = True
            # What an ensemble would actually output is one fix, not two, so
            # correctness is scored on the fix it would emit -- the mean of the
            # two translations. Counting the frame right because *either* arm
            # was right would score a fix nobody proposed.
            dx = (ra["dx"] + rb["dx"]) / 2
            dy = (ra["dy"] + rb["dy"]) / 2
            right[i] = np.hypot(dx + OFFSET, dy) < TOL_PX
        prec = right.sum() / ok.sum() if ok.sum() else float("nan")
        rec = right.sum() / union.sum() if union.sum() else float("nan")
        agree_stats[f"{a}+{b}"] = {"kabul": int(ok.sum()), "dogru": int(right.sum()),
                                   "kesinlik": float(prec), "duyarlilik": float(rec)}
        print(f"{a + ' + ' + b:26s} {ok.sum():7d} {prec * 100:8.0f}% {rec * 100:10.0f}%")
    print("-" * 62)
    print("kesinlik = kabul edilenlerin ne kadari dogru")
    print("duyarlilik = bulunabilir dogru fix'lerin ne kadari yakalaniyor")

    (OUT / f"06_uzlasma_{n}.json").write_text(json.dumps({
        "n": n, "tol_px": TOL_PX, "agree_px": AGREE_PX, "temsiller": REPS,
        "ozet": {
            "dogru_orani": {k: float(v.mean()) for k, v in correct.items()},
            "sadece_bu": only,
            "birlesim": float(union.mean()),
            "kesisim": float(every.mean()),
            "uzlasma": agree_stats,
        },
        "kareler": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT / f'06_uzlasma_{n}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

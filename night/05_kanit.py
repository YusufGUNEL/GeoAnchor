"""The night failure, shown rather than tabulated.

The numbers in 01 and 02 say LoFTR scores zero at night, that RoMa answers every
frame and is wrong on most of them, and that a band-passed representation moves
the needle. Those are three claims a reader has to take on trust. This script
turns them into one picture each, on the same pair of images, so the reader can
check them by looking.

Two figures:

  30_gece_neden.png   why raw matching cannot work -- the same place in thermal
                      and in satellite, first as captured, then band-passed.
                      Nothing about the brightness is shared; the edges are.

  31_gece_kanit.png   what each arm actually does with that pair. Match lines
                      drawn where the matcher put them, and on the satellite
                      half the patch centre: a cyan cross for where the thermal
                      frame truly sits, a dot for where the arm puts it, and
                      the distance between them. A wrong fix is not slightly
                      off, it is somewhere else entirely.

The pair is not hand-picked to flatter the system. The script scans candidates
and takes the first one on which all three row captions are simultaneously
true: LoFTR blind, RoMa on raw input confidently wrong, RoMa on clahe+dog
correct. Requiring the middle condition matters -- RoMa is right on 2% of raw
frames, and illustrating row 2 with one of those would put "confidently wrong"
next to a correct answer. If no such pair exists in the scanned range the
script says so rather than quietly showing something else, and the population
rates in the captions are read from night/sonuclar/ rather than typed in. The
chosen index is printed and written into the figure caption.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

import cv2
import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "night"))
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

from src.figtext import figdir, pct, pick                     # noqa: E402
from src.matching import estimate_similarity                 # noqa: E402

kopru = import_module("02_kopru")

DATA = ROOT / "night" / "veri" / "thermal_dataset"
FIG = figdir()

T = pick({
 "en": {
  "why_title": ("Same place, two modalities: BRIGHTNESS IS NOT SHARED, STRUCTURE IS\n"
                "Top, as captured — the two frames are {off} px apart and the ground "
                "texture is not the same thing on both sides.\n"
                "Bottom, after the band-pass — roads, field boundaries and building "
                "outlines survive on both."),
  "thermal": "THERMAL — what the camera sees",
  "sat": "SATELLITE — what the map shows",
  "thermal_dog": "thermal, clahe+dog",
  "sat_dog": "satellite, clahe+dog",
  "ev_title": ("Night thermal localization: how the daylight system fails, and what "
               "moves the needle\nEach row: thermal left, satellite right; lines are "
               "the correspondences the matcher proposed.\nOn the satellite half a "
               "CYAN CROSS is the true place and a DOT is the estimate. One and the "
               "same pair (scan index {k})."),
  "truth": "true place",
  "est": "estimate",
  "row1": "1) LoFTR, raw input — the daylight system as it stands",
  "row1n": ("{raw} raw correspondences, none survive RANSAC ({n} inliers).\n"
            "No estimate is produced: the system is BLIND. Correct on {rate} of "
            "{total} frames."),
  "row2": "2) RoMa, raw input — a stronger matcher",
  "row2n": ("{n} inliers, error {err:.0f} px.\n"
            "Confident and WRONG: it answers every frame, {rate} of them correctly."),
  "row3": "3) RoMa + clahe+dog — appearance discarded, structure kept",
  "row3n": ("{n} inliers, error {err:.1f} px (inside the {tol:.0f} px tolerance).\n"
            "{rate} of frames look like this."),
 },
 "tr": {
  "why_title": ("Ayni yer, iki kip: PARLAKLIK ORTAK DEGIL, YAPI ORTAK\n"
                "Ustte ham goruntuler — iki kare arasinda {off} px gercek kayma var; "
                "zemin dokusu iki tarafta ayni sey degil.\n"
                "Altta bant-gecirenden sonra — yollar, tarla sinirlari ve bina "
                "hatlari iki tarafta da cikiyor."),
  "thermal": "TERMAL — kameranin gordugu",
  "sat": "UYDU — haritanin gosterdigi",
  "thermal_dog": "termal, clahe+dog",
  "sat_dog": "uydu, clahe+dog",
  "ev_title": ("Gece termal konumlandirma: gunduz sisteminin cokusu ve neyin ibreyi "
               "kaldirdigi\nHer satirda solda termal, sagda uydu; cizgiler "
               "esleyicinin kurdugu karsiliklar.\nUydu tarafinda MAVI ARTI = gercek "
               "yer, DAIRE = kestirilen yer. Tek ve ayni cift (tarama indeksi {k})."),
  "truth": "gercek yer",
  "est": "kestirilen yer",
  "row1": "1) LoFTR, ham goruntu — gunduz sistemi oldugu gibi",
  "row1n": ("{raw} ham karsilik, RANSAC'i geceni yok ({n} ic nokta).\n"
            "Kestirim uretilemiyor: sistem KOR. {total} karede dogru konum orani "
            "{rate}."),
  "row2": "2) RoMa, ham goruntu — daha guclu esleyici",
  "row2n": ("{n} ic nokta, hata {err:.0f} px.\n"
            "Kendinden emin ve YANLIS: her kareyi kabul ediyor, {rate}'si dogru."),
  "row3": "3) RoMa + clahe+dog — gorunum atildi, yapi kaldi",
  "row3n": ("{n} ic nokta, hata {err:.1f} px ({tol:.0f} px toleransin altinda).\n"
            "Karelerin {rate}'sinda boyle."),
 },
})
OUT = ROOT / "night" / "sonuclar"
OFFSET = kopru.OFFSET
TOL_PX = 20.0
# Skip flags such as --tr so the language switch and the scan size can be
# passed together.
_args = [a for a in sys.argv[1:] if not a.startswith("-")]
N_SCAN = int(_args[0]) if _args else 40
MAX_LINES = 70

CYAN, GREEN, RED = "#00d4ff", "#00b894", "#ff2d55"


def global_rates() -> dict:
    """The population numbers quoted in the row captions.

    Read from the runs that measured them rather than typed in, so a caption
    cannot end up disagreeing with night/sonuclar/.
    """
    taban = json.loads((OUT / "01_taban.json").read_text(encoding="utf-8"))
    roma = json.loads((OUT / "02_kopru_roma.json").read_text(encoding="utf-8"))
    by_arm = {r["kol"]: r for r in taban}
    loftr = by_arm["termal->uydu (LoFTR)"]
    roma_ham = by_arm["termal->uydu (RoMa)"]
    dog = next(r for r in roma if r["temsil"] == "clahe+dog")
    return {
        "n": int(loftr["cift"]),
        "loftr_dogru": loftr["dogru_konum_orani"],
        "roma_ham_dogru": roma_ham["dogru_konum_orani"],
        "roma_dog_dogru": dog["dogru_konum_orani"],
    }


def truth_M() -> np.ndarray:
    """Thermal index i and satellite index j are the same ground point offset by
    OFFSET grid units, and one grid unit is one pixel along the image x axis
    (measured in 00_olcek.py). So the correct transform is a pure translation."""
    return np.array([[1.0, 0.0, -OFFSET], [0.0, 1.0, 0.0]])


def run_arm(matcher, rep, thermal, satellite):
    a, b = rep(thermal, True), rep(satellite, False)
    pa, pb, _ = matcher.match(a, b)
    M, mask, n = estimate_similarity(pa, pb)
    err = None if M is None else float(np.hypot(M[0, 2] + OFFSET, M[1, 2]))
    keep = np.ones(len(pa), bool) if mask is None else mask.ravel().astype(bool)
    return {"a": a, "b": b, "pa": pa, "pb": pb, "keep": keep,
            "M": M, "n": n, "err": err}


def centre(shape, M) -> np.ndarray:
    """Where the middle of the thermal patch lands under M."""
    h, w = shape[:2]
    c = np.array([[w / 2, h / 2]], dtype=np.float32)
    return (c @ M[:, :2].T + M[:, 2])[0]


def draw_row(ax, arm, title, note):
    a, b = arm["a"], arm["b"]
    h, w = a.shape[:2]
    canvas = np.hstack([cv2.cvtColor(a, cv2.COLOR_GRAY2RGB),
                        cv2.cvtColor(b, cv2.COLOR_GRAY2RGB)])
    ax.imshow(canvas)
    ax.axvline(w, color="w", lw=1.5)

    pa, pb, keep = arm["pa"], arm["pb"], arm["keep"]
    ok = arm["err"] is not None and arm["err"] < TOL_PX
    if len(pa):
        idx = np.where(keep)[0] if keep.any() else np.arange(len(pa))
        if len(idx) > MAX_LINES:
            idx = idx[np.linspace(0, len(idx) - 1, MAX_LINES).astype(int)]
        ax.plot(np.stack([pa[idx, 0], pb[idx, 0] + w]),
                np.stack([pa[idx, 1], pb[idx, 1]]),
                color=GREEN if ok else RED, lw=0.6, alpha=0.5)

    # Marking the patch centre rather than its outline: at a 70 px offset the
    # outline runs off the satellite tile and back across the thermal panel,
    # which reads as a drawing error rather than as a position.
    shift = np.array([w, 0.0])
    ct = centre(a.shape, truth_M()) + shift
    ax.plot(*ct, "+", color=CYAN, ms=17, mew=2.6, zorder=6, label=T["truth"])
    if arm["M"] is not None:
        ce = centre(a.shape, arm["M"]) + shift
        col = GREEN if ok else RED
        ax.plot([ct[0], ce[0]], [ct[1], ce[1]], "-", color=col, lw=1.6, zorder=6)
        ax.plot(*ce, "o", color=col, ms=9, mec="k", mew=0.8, zorder=7,
                label=T["est"])
        ax.annotate(f"{arm['err']:.0f} px", ce, textcoords="offset points",
                    xytext=(11, -4), color="w", fontsize=10, zorder=8,
                    bbox=dict(fc=col, ec="none", alpha=0.9, pad=2.0))

    ax.set_xlim(0, 2 * w)
    ax.set_ylim(h, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=12, loc="left", pad=6)
    ax.text(0.995, 0.03, note, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=10.5, color="w",
            bbox=dict(fc="#2d3436", ec="none", alpha=0.82, pad=4.5))


def main() -> int:
    FIG.mkdir(exist_ok=True)
    import torch
    from src.matching import LoFTRMatcher, RomaMatcher

    with h5py.File(DATA / "test_database.h5", "r") as sat, \
         h5py.File(DATA / "test_queries.h5", "r") as thr:
        pairs = kopru.build_pairs(kopru.coords(sat), N_SCAN)
        thr_imgs = [kopru.gray(thr["image_data"][i]) for i, _ in pairs]
        sat_imgs = [kopru.gray(sat["image_data"][j]) for _, j in pairs]
    print(f"{len(pairs)} aday cift taranacak, gercek kayma {OFFSET} px\n", flush=True)

    ham, dog = kopru.REPS["ham"], kopru.REPS["clahe+dog"]

    # LoFTR needs 1.4 GB and RoMa 2.7 GB; together they do not fit on a 4 GB
    # card. So the LoFTR pass runs over every candidate first and the model is
    # released before RoMa is built. This also narrows the RoMa pass to the
    # frames that can still produce the illustration we are looking for.
    loftr = LoFTRMatcher(device="cuda")
    loftr_arms = [run_arm(loftr, ham, t, s) for t, s in zip(thr_imgs, sat_imgs)]
    blind = [k for k, a in enumerate(loftr_arms) if a["M"] is None or a["n"] == 0]
    print(f"LoFTR {len(blind)}/{len(pairs)} karede tamamen kor\n", flush=True)
    del loftr
    torch.cuda.empty_cache()

    if not blind:
        print("LoFTR hicbir karede kor degil -- taban cizgisi degismis, once 01'i tekrar kos.")
        return 1

    roma = RomaMatcher(device="cuda")
    chosen = None
    for pos, k in enumerate(blind):
        t, s = thr_imgs[k], sat_imgs[k]
        arms = {"loftr_ham": loftr_arms[k],
                "roma_ham": run_arm(roma, ham, t, s),
                "roma_dog": run_arm(roma, dog, t, s)}
        e_ham, e_dog = arms["roma_ham"]["err"], arms["roma_dog"]["err"]
        # All three rows have to be true of this one pair. RoMa on raw input is
        # right on 2% of frames, and landing on one of those would leave row 2
        # captioned "confidently wrong" next to a correct answer.
        wrong = e_ham is None or e_ham >= TOL_PX
        fixed = e_dog is not None and e_dog < TOL_PX
        fmt = lambda e: "-" if e is None else format(e, "7.1f") + " px"
        print(f"  {pos + 1}/{len(blind)}  cift {k:3d}  roma ham {fmt(e_ham)}   "
              f"roma+dog {fmt(e_dog)}{'   <= secildi' if (wrong and fixed) else ''}",
              flush=True)
        if wrong and fixed:
            chosen = (k, t, s, arms)
            break

    if chosen is None:
        print(f"\n{len(pairs)} cift icinde uc kolu birden gosteren ornek yok "
              "(LoFTR kor + RoMa ham yanlis + clahe+dog dogru).")
        print("N_SCAN'i buyutup tekrar dene; uydurma bir ornek gosterilmeyecek.")
        return 1

    k, t_raw, s_raw, arms = chosen
    print(f"\nsecilen cift: tarama indeksi {k}\n")

    # ---- figure 30: why raw matching cannot work ------------------------
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 10.9))
    panels = [(t_raw, T["thermal"], axes[0, 0]),
              (s_raw, T["sat"], axes[0, 1]),
              (dog(t_raw, True), T["thermal_dog"], axes[1, 0]),
              (dog(s_raw, False), T["sat_dog"], axes[1, 1])]
    for img, name, ax in panels:
        ax.imshow(img, cmap="gray")
        ax.set_title(name, fontsize=12)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(T["why_title"].format(off=OFFSET), fontsize=12, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.935), h_pad=2.2)
    fig.savefig(FIG / "30_gece_neden.png", dpi=115, bbox_inches="tight")
    plt.close(fig)
    print(f"-> {FIG / '30_gece_neden.png'}")

    # ---- figure 31: what each arm does ----------------------------------
    a0, a1, a2 = arms["loftr_ham"], arms["roma_ham"], arms["roma_dog"]
    g = global_rates()
    rows = [
        (a0, T["row1"], T["row1n"].format(
            raw=len(a0["pa"]), n=a0["n"], total=g["n"],
            rate=pct(100 * g["loftr_dogru"]))),
        (a1, T["row2"], T["row2n"].format(
            n=a1["n"], err=a1["err"], rate=pct(100 * g["roma_ham_dogru"]))),
        (a2, T["row3"], T["row3n"].format(
            n=a2["n"], err=a2["err"], tol=TOL_PX,
            rate=pct(100 * g["roma_dog_dogru"]))),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(11.6, 15.4))
    for ax, (arm, title, note) in zip(axes, rows):
        draw_row(ax, arm, title, note)
    # Row 2 is the only one carrying both markers, so the legend goes there.
    axes[1].legend(loc="upper right", fontsize=10, framealpha=0.85)
    fig.suptitle(T["ev_title"].format(k=k), fontsize=12, y=0.998)
    fig.tight_layout(rect=(0, 0, 1, 0.968), h_pad=1.6)
    fig.savefig(FIG / "31_gece_kanit.png", dpi=112, bbox_inches="tight")
    plt.close(fig)
    print(f"-> {FIG / '31_gece_kanit.png'}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "05_kanit.json").write_text(json.dumps({
        "tarama_indeksi": k,
        "taranan": len(pairs),
        "kollar": {n: {"ic_nokta": int(a["n"]), "hata_px": a["err"]}
                   for n, a in arms.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {OUT / '05_kanit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

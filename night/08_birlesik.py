"""If the tile says it will fail, do not match it.

07 found that a score computed from the satellite tile alone -- no flight, no
thermal frame, no matching -- separates the frames that will localise from the
ones that will not, at AUC 0.852. That is an explanation. This script asks
whether it is also a component.

The gate in 04 runs *after* matching: the matcher spends its 2.3 s, and then a
verification score decides whether to believe the answer. A pre-match score
changes the shape of the system, because it can decline before any of that
cost is paid, and because it is statistically independent of everything the
matcher reports -- it never saw the thermal frame.

Four gates, all scored the same way (threshold fitted on half the frames,
measured on the other half, 400 random splits, precision target 90%):

  sonra        the current gate: orientation agreement x inlier count
  once         the tile score on its own, decided before matching
  once VE sonra   both must pass -- the pre-gate removes hopeless tiles from
               the pool the post-gate then works on
  carpim       normalised product of the two, one threshold instead of two

Also reported: the fraction of frames the pre-gate lets through, which is the
fraction of the matcher's runtime that survives. Declining early is not only
about precision on a laptop GPU at 2.3 s a frame.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "night"))
sys.stdout.reconfigure(encoding="utf-8")

kapi = import_module("04_kapi")
yasa = import_module("07_yasa")

OUT = ROOT / "night" / "sonuclar"
TARGET = kapi.TARGET_PRECISION
ONCE_OLCUT = "uydu_yapi_skoru"       # basemap only; see 07
N_BOLME = 400


def z(v: np.ndarray) -> np.ndarray:
    return (v - v.mean()) / (v.std() + 1e-9)


def pre_gate_recall(pre: np.ndarray, labels: np.ndarray, keep_frac: float):
    """What a pre-match cut costs and saves at a given pass rate."""
    thr = np.quantile(pre, 1 - keep_frac)
    keep = pre >= thr
    return {
        "gecen_kare": float(keep.mean()),
        "korunan_dogru": float(labels[keep].sum() / max(labels.sum(), 1)),
        "esik": float(thr),
    }


def main() -> int:
    kayit = OUT / "03_dogrulama_1000.json"
    yasa_kayit = OUT / "07_yasa_1000.json"
    for f in (kayit, yasa_kayit):
        if not f.exists():
            raise SystemExit(f"{f.name} yok")

    rows = json.loads(kayit.read_text(encoding="utf-8"))["kareler"]
    yd = json.loads(yasa_kayit.read_text(encoding="utf-8"))
    labels = np.array([r["dogru"] for r in rows])
    n = len(rows)
    if yd["n"] != n:
        raise SystemExit(f"03 {n} kare, 07 {yd['n']} kare -- ayni kosu degil")
    if np.array(yd["dogru_etiket"]).tolist() != labels.tolist():
        raise SystemExit("iki dosyanin dogru/yanlis etiketleri ayni degil")

    ham = {k: np.array(v) for k, v in yd["ham_olcumler"].items()}
    pre = yasa.derive(ham)[ONCE_OLCUT]

    # The post-match score from 04: the product of the two signals that work.
    yon = np.array([r["yon_uyumu"] for r in rows])
    ic = np.array([r["ic_nokta"] for r in rows])
    post = (yon - yon.min()) / (np.ptp(yon) + 1e-9) * (ic / (ic.max() + 1e-9))

    print(f"{n} kare, {labels.sum()} dogru (%{100 * labels.mean():.1f})")
    print(f"on-kapi olcutu: {ONCE_OLCUT}  (AUC {yd['ozet'][ONCE_OLCUT]['auc']:.3f})\n")

    print("On-kapinin bedeli: kac kareyi eleyip kac dogru fix'i koruyor")
    print("-" * 62)
    print(f"{'gecen kare':>12s} {'korunan dogru fix':>20s} {'elenen eslesme':>18s}")
    for frac in (0.7, 0.5, 0.3, 0.2, 0.1):
        g = pre_gate_recall(pre, labels, frac)
        print(f"{g['gecen_kare'] * 100:11.0f}% {g['korunan_dogru'] * 100:19.0f}%"
              f" {100 * (1 - g['gecen_kare']):17.0f}%")
    print()

    # Both-must-pass needs a pre-threshold before the post-threshold is fitted,
    # so it is fixed at the pass rate that keeps nearly every correct fix. The
    # point is to shrink the pool, not to do the deciding.
    kalsin = 0.5
    pre_thr = np.quantile(pre, 1 - kalsin)
    korunan = labels[pre >= pre_thr].sum() / labels.sum()

    def unit(v):
        return (v - v.min()) / (np.ptp(v) + 1e-9)

    adaylar = {
        "sonra (04'un kapisi)": post,
        "once (sadece karo)": pre,
        "carpim (once x sonra)": unit(pre) * unit(post),
    }

    print("=" * 78)
    print(f"{'kapi':26s} {'ornek-ici':>20s} {'AYRIK KUMEDE':>28s}")
    print(f"{'':26s} {'kesinlik':>9s} {'duyar.':>10s} {'kesinlik (p10)':>18s} {'duyar.':>9s}")
    print("-" * 78)
    best = {}
    for name, score in adaylar.items():
        ins = kapi.best_at_precision(score, labels, True, TARGET)
        out = kapi.held_out(score, labels, True, TARGET, repeats=N_BOLME)
        best[name] = {"ornek_ici": ins, "ayrik": out}
        if ins is None or out is None:
            print(f"{name:26s} {'%90 kesinlige ulasilamiyor':>20s}")
            continue
        print(f"{name:26s} {ins['kesinlik'] * 100:8.0f}% {ins['duyarlilik'] * 100:9.0f}%"
              f" {out['kesinlik_medyan'] * 100:11.0f}% ({out['kesinlik_p10'] * 100:3.0f}%)"
              f" {out['duyarlilik_medyan'] * 100:8.0f}%")

    # "Both must pass" is scored on the surviving pool but recall is still
    # reported against every correct fix in the flight -- the frames the
    # pre-gate threw away are lost, and the number has to show that.
    pool = pre >= pre_thr
    ins = kapi.best_at_precision(post[pool], labels[pool], True, TARGET)
    out = kapi.held_out(post[pool], labels[pool], True, TARGET, repeats=N_BOLME)
    name = f"once VE sonra (%{kalsin * 100:.0f} gecis)"
    if ins and out:
        best[name] = {"ornek_ici": ins, "ayrik": out,
                      "on_kapi_esigi": float(pre_thr),
                      "on_kapi_korunan_dogru": float(korunan)}
        print(f"{name:26s} {ins['kesinlik'] * 100:8.0f}% "
              f"{ins['duyarlilik'] * korunan * 100:9.0f}%"
              f" {out['kesinlik_medyan'] * 100:11.0f}% ({out['kesinlik_p10'] * 100:3.0f}%)"
              f" {out['duyarlilik_medyan'] * korunan * 100:8.0f}%")
    print("=" * 78)
    print(f"'once VE sonra' duyarliligi tum dogru fix'lere gore olcek edildi: "
          f"on-kapi bunlarin %{korunan * 100:.0f}'ini gecirdi.")
    print("esikler karelerin yarisinda secilip diger yarisinda olculuyor, "
          f"{N_BOLME} rastgele bolme.")

    # --- consensus, and what the pre-gate does to it ---------------------
    # 06 accepts a fix when two representations independently land within
    # 20 px of each other. That has no fitted threshold at all, so it needs no
    # split: precision and recall are read directly. The open question is
    # whether the pre-gate, which is independent of both matchers, lifts its
    # precision without costing the recall that makes it interesting.
    uz_kayit = OUT / f"06_uzlasma_{n}.json"
    uzlasma = None
    if uz_kayit.exists():
        ud = json.loads(uz_kayit.read_text(encoding="utf-8"))
        reps = ud["temsiller"]
        if len(reps) == 2 and ud["n"] == n:
            a, b = reps
            agree = np.zeros(n, bool)
            agree_right = np.zeros(n, bool)
            for i, row in enumerate(ud["kareler"]):
                ra, rb = row[a], row[b]
                if not (ra.get("var") and rb.get("var")):
                    continue
                if np.hypot(ra["dx"] - rb["dx"], ra["dy"] - rb["dy"]) >= ud["agree_px"]:
                    continue
                agree[i] = True
                dx, dy = (ra["dx"] + rb["dx"]) / 2, (ra["dy"] + rb["dy"]) / 2
                agree_right[i] = np.hypot(dx + 70, dy) < 20.0
            # Recall is against every fix this pair could have found, which is
            # the union of the two arms -- not the 03 run's 86, since these are
            # different representations.
            union = np.array([row[a].get("dogru", False) or row[b].get("dogru", False)
                              for row in ud["kareler"]])

            print(f"\nUzlasma kapisi ({a} + {b}, ayarlanacak esik yok) ve on-kapiyla")
            print("-" * 74)
            print(f"{'on-kapi gecisi':>16s} {'kabul':>7s} {'kesinlik':>10s} "
                  f"{'duyarlilik':>12s} {'dogru cikan kare':>18s} {'maliyet':>9s}")
            uzlasma = {}
            for frac in (1.0, 0.7, 0.5, 0.3):
                m = agree if frac >= 1.0 else agree & (pre >= np.quantile(pre, 1 - frac))
                kabul, dogru = int(m.sum()), int((m & agree_right).sum())
                prec = dogru / kabul if kabul else float("nan")
                rec = dogru / union.sum() if union.sum() else float("nan")
                # Consensus needs two RoMa passes per frame it looks at, and the
                # pre-gate decides how many frames that is. Baseline is one pass
                # on every frame, so the unit is "RoMa calls per frame of flight".
                maliyet = 2.0 * min(frac, 1.0)
                etiket = "yok" if frac >= 1.0 else f"%{frac * 100:.0f}"
                uzlasma[etiket] = {"kabul": kabul, "dogru": dogru,
                                   "kesinlik": float(prec), "duyarlilik": float(rec),
                                   "dogru_kare_orani": dogru / n,
                                   "roma_cagrisi_kare_basina": maliyet}
                print(f"{etiket:>16s} {kabul:7d} {prec * 100:9.0f}% {rec * 100:11.0f}%"
                      f" {100 * dogru / n:17.1f}% {maliyet:8.1f}x")
            print("-" * 74)
            print(f"duyarlilik paydasi: bu iki kolun birlikte bulabildigi "
                  f"{int(union.sum())} dogru fix.")
            print("dogru cikan kare: 1000 karenin yuzde kaci hem kabul edildi hem dogru.")
            print("maliyet: kare basina RoMa cagrisi; taban cizgisi (tek temsil, "
                  "her kare) 1.0x.")

    (OUT / f"08_birlesik_{n}.json").write_text(json.dumps(
        {"n": n, "dogru": int(labels.sum()), "once_olcut": ONCE_OLCUT,
         "on_kapi_gecis": kalsin, "on_kapi_korunan_dogru": float(korunan),
         "kapilar": best, "uzlasma": uzlasma}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"\n-> {OUT / f'08_birlesik_{n}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

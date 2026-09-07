"""Is training a cross-modal matcher worth it? Split the failures and see.

07 established that tile content predicts which night frames localise, and 12
concluded from that a trained matcher was unlikely to help. That conclusion was
reasoning, not measurement, and it left the project's only open research
direction resting on a hunch.

The measurement that settles it is already available in the cached per-frame
scores. The top structure decile still fails on most of its frames. Two very
different things could be happening there:

  content, still     the satellite tile is rich but the THERMAL frame is not --
                     the sensor never captured the structure the map has, so
                     there is no correspondence for any matcher to find and
                     training buys nothing
  matcher            both sides are rich and aligned by construction, and the
                     matcher still misses -- the correspondence exists and is
                     not being found, which is exactly what training fixes

Separating them needs no GPU: 07 stored the structure score for each side, and
03 stored whether each frame was located. The frames where BOTH sides score
high and the answer is still wrong are the training-addressable population, and
their count is the size of the prize.

    python night/09_tavan.py
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

OUT = ROOT / "night" / "sonuclar"
yasa = import_module("07_yasa")

DECILE = 10


def band(score: np.ndarray, top_frac: float) -> np.ndarray:
    """Mask of the top `top_frac` of frames by this score."""
    return score >= np.quantile(score, 1 - top_frac)


def main() -> int:
    dog_p, yasa_p = OUT / "03_dogrulama_1000.json", OUT / "07_yasa_1000.json"
    for p in (dog_p, yasa_p):
        if not p.exists():
            raise SystemExit(f"{p.name} yok")

    rows = json.loads(dog_p.read_text(encoding="utf-8"))["kareler"]
    yd = json.loads(yasa_p.read_text(encoding="utf-8"))
    labels = np.array([r["dogru"] for r in rows])
    n = len(rows)
    if yd["n"] != n:
        raise SystemExit("iki kosu ayni degil")

    ham = {k: np.array(v) for k, v in yd["ham_olcumler"].items()}
    vals = yasa.derive(ham)

    def z(v):
        return (v - v.mean()) / (v.std() + 1e-9)

    sat = z(ham["uydu_kenar_yogunlugu"]) - z(ham["uydu_yuksek_frekans"])
    thr = z(ham["termal_kenar_yogunlugu"]) - z(ham["termal_yuksek_frekans"])

    print(f"{n} kare, {labels.sum()} dogru (%{100 * labels.mean():.1f})\n")

    # --- where do the failures sit? -------------------------------------
    print("Uydu karosu yapili oldugunda, basarisizliklarin termal tarafi nasil?")
    print("-" * 68)
    print(f"{'uydu yapisi':>14s} {'kare':>6s} {'dogru':>7s} "
          f"{'basarisizlarin termal ort.':>28s}")
    for frac, ad in ((0.1, "en iyi %10"), (0.3, "en iyi %30"), (1.0, "hepsi")):
        m = band(sat, frac)
        fail = m & ~labels
        print(f"{ad:>14s} {int(m.sum()):6d} {labels[m].mean() * 100:6.0f}% "
              f"{thr[fail].mean():28.2f}")
    print(f"{'':14s} {'':6s} {'':7s} {'(dogrularin termal ort.: ' + f'{thr[labels].mean():.2f})':>28s}")

    # --- the population a trained matcher could actually address ---------
    print("\nHer iki taraf da yapiliyken ne oluyor?")
    print("-" * 68)
    print(f"{'esik':>14s} {'kare':>6s} {'dogru':>7s} {'basarisiz':>10s} "
          f"{'karelerin %':>12s}")
    ozet = {}
    for frac in (0.30, 0.20, 0.10):
        m = band(sat, frac) & band(thr, frac)
        if m.sum() == 0:
            continue
        fail = int((m & ~labels).sum())
        ozet[f"%{frac * 100:.0f}"] = {
            "kare": int(m.sum()), "dogru": int(labels[m].sum()),
            "basarisiz": fail, "dogru_orani": float(labels[m].mean()),
            "basarisiz_kare_orani": fail / n,
        }
        print(f"{'ikisi de en iyi %' + f'{frac * 100:.0f}':>14s} {int(m.sum()):6d} "
              f"{labels[m].mean() * 100:6.0f}% {fail:10d} {100 * fail / n:11.1f}%")

    # --- the verdict -----------------------------------------------------
    key = "%30"
    if key in ozet:
        o = ozet[key]
        print("\n" + "=" * 68)
        print(f"Egitimin hedefleyebilecegi nufus: {o['basarisiz']} kare "
              f"(%{100 * o['basarisiz_kare_orani']:.1f})")
        print("Bu karelerde iki tarafta da yapi var ve hizalama zaten dogru;")
        print("karsilik mevcut ve bulunamiyor -- egitimin duzelttigi sey tam bu.")
        print()
        tavan = labels.mean() + o["basarisiz_kare_orani"]
        print(f"Kusursuz bir esleyici bile en fazla %{100 * labels.mean():.1f} "
              f"-> %{100 * tavan:.1f} yapabilir")
        print("(gerisi, bir tarafinda yapi olmayan kareler; orada bulunacak")
        print(" ortak bir sey yok ve egitim de onu uretemez)")
        print("=" * 68)

    (OUT / f"09_tavan_{n}.json").write_text(json.dumps(
        {"n": n, "dogru": int(labels.sum()),
         "taban_dogru_orani": float(labels.mean()),
         "her_iki_taraf": ozet}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT / f'09_tavan_{n}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

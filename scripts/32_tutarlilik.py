"""Do the documents still say what the result files say?

The README claims every number in it comes from `results/`, and the paper
claims the same. Nothing enforced that. Numbers get quoted in five places --
README.md, README.tr.md, both manuscripts and night/DURUM.md -- and a rerun
that shifts a median leaves most of them stale and confident.

This script re-derives the headline numbers from the JSON and NPZ files and
checks that each document still contains them, in that document's own notation.
Three conventions have to be handled or the checker reports its own formatting
as an error:

  decimal separator   the Turkish files write 8,35 where the English write 8.35
  percent sign        Turkish puts it first: %95 against 95%
  LaTeX escapes       the manuscript writes 95\\% and 8.35\\,m

It is a spelling check against reality, not a rerun: it does not recompute the
pipeline, it reads what the pipeline last wrote. Exit code 1 if any claim is
missing, so it can gate a commit.

A number the checker cannot find is not automatically a lie -- it may have been
rephrased. But it does mean nobody can tell any more without going back to the
data, which is the situation this is meant to prevent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
NIGHT = ROOT / "night" / "sonuclar"

EN = ROOT / "README.md"
TR = ROOT / "README.tr.md"
TEX = ROOT / "paper" / "geoanchor.tex"
SIU = ROOT / "paper" / "siu" / "siu_geoanchor.tex"
DURUM = ROOT / "night" / "DURUM.md"
FILES = (EN, TR, TEX, DURUM, SIU)
TURKISH = {TR, DURUM, SIU}   # comma decimals, percent sign leading


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def needle(value: float, digits: int, f: Path, pct: bool = False) -> str:
    """The number as that document would spell it."""
    s = f"{value:.{digits}f}"
    if f in TURKISH:
        s = s.replace(".", ",")
        return f"%{s}" if pct else s
    return f"{s}%" if pct else s


class Claims:
    """Each claim is one value, checked in every file that should quote it."""

    def __init__(self):
        self.rows: list[tuple[str, float, int, bool, list[Path]]] = []

    def add(self, label, value, digits, files, pct=False):
        self.rows.append((label, value, digits, pct, list(files)))


def build() -> Claims:
    c = Claims()
    multi = load(RES / "20_multiflight.json")
    zorluk = load(RES / "21_flight_difficulty.json")
    ozet = load(RES / "22_summary.json")

    # --- the ten-flight table --------------------------------------------
    for fid, row in sorted(multi.items()):
        if row.get("durum") == "tamam":
            c.add(f"ucus {fid} medyan", row["medyan_m"], 2, [EN, TR, SIU])
    c.add("en iyi ucus", ozet["en_iyi"], 2, [EN, TEX])
    c.add("en kotu ucus", ozet["en_kotu"], 2, [EN, TEX])

    # --- the law ----------------------------------------------------------
    ids = sorted(zorluk)
    x = np.array([zorluk[i]["tutma_orani"] * 100 for i in ids])
    y = np.array([zorluk[i]["medyan_hata_m"] for i in ids])
    c.add("korelasyon", abs(float(np.corrcoef(x, np.log10(y))[0, 1])), 3,
          [EN, TR, TEX, SIU])

    # --- odometry drift on flight 03 --------------------------------------
    vo = np.load(RES / "06_odometry.npz")
    c.add("odometri son hata", float(vo["err"][-1]), 0, [EN, TR, TEX, SIU])

    # --- night: verification ----------------------------------------------
    dog = load(NIGHT / "03_dogrulama_1000.json")
    rows = dog["kareler"]
    c.add("gece dogru fix orani", 100 * sum(r["dogru"] for r in rows) / len(rows), 1,
          [EN, TR, TEX, DURUM])
    # The paper quotes the inlier count because that is the comparison its night
    # subsection makes; orientation agreement appears only in the READMEs.
    c.add("yon uyumu AUC", dog["ozet"]["yon_uyumu"]["auc"], 3, [EN, TR, DURUM])
    c.add("ic nokta AUC", dog["ozet"]["ic_nokta"]["auc"], 3, [EN, TR, TEX, DURUM])

    yasa = load(NIGHT / "07_yasa_1000.json")
    c.add("yapi skoru AUC", yasa["ozet"][yasa["en_iyi_uydu"]]["auc"], 3,
          [EN, TR, TEX, DURUM])

    # --- night: gates -------------------------------------------------------
    kapi = load(NIGHT / "08_birlesik_1000.json")
    carpim = kapi["kapilar"]["carpim (once x sonra)"]["ayrik"]
    c.add("carpim kapi kesinlik", carpim["kesinlik_medyan"] * 100, 0, [EN, TR], pct=True)
    c.add("carpim kapi duyarlilik", carpim["duyarlilik_medyan"] * 100, 0, [EN, TR], pct=True)

    en_iyi = kapi["uzlasma"]["%30"]          # the operating point every doc quotes
    c.add("uzlasma+on-kapi kesinlik", en_iyi["kesinlik"] * 100, 0,
          [EN, TR, TEX, DURUM], pct=True)
    c.add("uzlasma+on-kapi dogru kare", en_iyi["dogru_kare_orani"] * 100, 1,
          [EN, TR, TEX, DURUM])

    uz = load(NIGHT / "06_uzlasma_1000.json")["ozet"]["uzlasma"]["dog+sobel"]
    c.add("uzlasma ham kesinlik", uz["kesinlik"] * 100, 0, [EN, TR, DURUM], pct=True)
    c.add("uzlasma ham duyarlilik", uz["duyarlilik"] * 100, 0, [EN, TR, DURUM], pct=True)

    # --- the measured ceiling on training ----------------------------------
    tavan = load(NIGHT / "09_tavan_1000.json")
    o = tavan["her_iki_taraf"]["%30"]
    c.add("egitilebilir nufus", o["basarisiz"], 0, [EN, TR, DURUM])
    c.add("tavan", 100 * (tavan["taban_dogru_orani"] + o["basarisiz_kare_orani"]), 1,
          [EN, TR, DURUM])

    return c


def main() -> int:
    # Strip the typesetting so a claim is judged on the number. Three idioms
    # matter: IEEEtran's thin space before a unit, the escaped percent sign,
    # and the braced comma the Turkish manuscript needs in maths mode so
    # that 0{,}764 is not read as a separator.
    texts = {p: p.read_text(encoding="utf-8")
             .replace("\\,", "").replace("\\%", "%")
             .replace("{,}", ",").replace(" ", " ")
             for p in FILES}
    claims = build()

    missing = []
    for label, value, digits, pct, files in claims.rows:
        for f in files:
            if needle(value, digits, f, pct) not in texts[f]:
                missing.append((label, needle(value, digits, f, pct), f))
    checks = sum(len(r[4]) for r in claims.rows)
    width = max(len(r[0]) for r in claims.rows) + 2
    print(f"{len(claims.rows)} iddia, {checks} dosya kontrolu\n")
    if missing:
        for label, n, f in missing:
            print(f"  EKSIK  {label:{width}s} '{n}' -> {f.relative_to(ROOT)}")
        print(f"\n{len(missing)} iddia belgede bulunamadi.")
        print("Ya sayi degisti ve belge guncellenmedi, ya da ifade degisti.")
        print("Ikisi de elle bakmayi gerektirir; sessizce gecmemesi icin buradalar.")
        return 1

    for label, value, digits, pct, files in claims.rows:
        shown = needle(value, digits, EN, pct)
        print(f"  ok  {label:{width}s} {shown:>9s}  "
              f"{', '.join(f.name for f in files)}")
    print("\nHepsi tutuyor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

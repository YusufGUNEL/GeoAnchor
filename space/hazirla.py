"""Rebuild the Space's assets from the repository's own results.

The Space needs a handful of files that already exist elsewhere in the repo --
the per-flight result arrays and the demo video. Copying them in by hand works
once and then rots, and committing a second copy puts 17 MB of duplicated video
in the history. So the folder is generated instead, and `space/assets/` stays
out of git.

The night results are not copied but distilled: `night/sonuclar/` carries the
per-frame arrays every run wrote, which is right for re-analysis and wrong for
a page that only draws four charts. `30_gece.json` is the summary those charts
need, built here so the Space can never quote a number the results no longer
support.

    python space/hazirla.py     # then push space/ to the Hugging Face Space
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "space" / "assets"
NIGHT = ROOT / "night" / "sonuclar"
ASSETS.mkdir(parents=True, exist_ok=True)

wanted = sorted((ROOT / "results").glob("20_flight_[0-9][0-9].npz")) + [
    ROOT / "results" / "20_multiflight.json",
    ROOT / "results" / "21_flight_difficulty.json",
    ROOT / "figures" / "demo.mp4",
    ROOT / "figures" / "31_gece_kanit.png",
]
for src in wanted:
    if src.exists():
        shutil.copyfile(src, ASSETS / src.name)
        print(f"  {src.name}")
    else:
        print(f"  EKSIK: {src}")


def load(name: str):
    p = NIGHT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def night_summary() -> dict | None:
    taban, kopru = load("01_taban.json"), load("02_kopru_roma.json")
    dog, yasa = load("03_dogrulama_1000.json"), load("07_yasa_1000.json")
    kapi = load("08_birlesik_1000.json")
    if not all((taban, kopru, dog, yasa, kapi)):
        return None

    arms = {r["kol"]: r for r in taban}
    loftr_sobel = next((r for r in (load("02_kopru_loftr.json") or [])
                        if r["temsil"] == "sobel"), None)
    roma_dog = next(r for r in kopru if r["temsil"] == "clahe+dog")
    return {
        "kollar": [
            {"ad": "LoFTR, raw thermal", "dogru": arms["termal->uydu (LoFTR)"]["dogru_konum_orani"]},
            {"ad": "RoMa, raw thermal", "dogru": arms["termal->uydu (RoMa)"]["dogru_konum_orani"]},
            *([{"ad": "LoFTR, Sobel", "dogru": loftr_sobel["dogru_konum_orani"]}]
              if loftr_sobel else []),
            {"ad": "RoMa, CLAHE+DoG", "dogru": roma_dog["dogru_konum_orani"]},
        ],
        "auc": {
            "gradient orientation agreement": {"v": dog["ozet"]["yon_uyumu"]["auc"], "ne": "after"},
            "inlier count": {"v": dog["ozet"]["ic_nokta"]["auc"], "ne": "after"},
            "mutual information": {"v": dog["ozet"]["mi"]["auc"], "ne": "after"},
            "tile structure score (basemap only)":
                {"v": yasa["ozet"][yasa["en_iyi_uydu"]]["auc"], "ne": "before"},
            "edge density (basemap only)":
                {"v": yasa["ozet"]["uydu_kenar_yogunlugu"]["auc"], "ne": "before"},
        },
        "decile": yasa["decile"]["dogru_orani"],
        "taban_dogru_orani": sum(r["dogru"] for r in dog["kareler"]) / len(dog["kareler"]),
        "calisma_noktalari": kapi["uzlasma"],
        "eski_kapi": kapi["kapilar"]["sonra (04'un kapisi)"]["ayrik"],
    }


gece = night_summary()
if gece:
    (ASSETS / "30_gece.json").write_text(
        json.dumps(gece, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  30_gece.json  (night/sonuclar/'dan ozetlendi)")
else:
    print("  ATLANDI: 30_gece.json -- night/sonuclar/ eksik, Space gece bolumunu gizler")

print(f"\n-> {ASSETS}")

"""Rebuild the Space's assets from the repository's own results.

The Space is a *static* page: Hugging Face only hosts Gradio on a paid plan,
and this app never needed a server anyway -- every number it shows was computed
offline and committed to results/. So the job here is to turn those result files
into one JSON the page can fetch, plus the two media files it embeds.

Two things are distilled rather than copied. The per-flight arrays live in NPZ
and the page cannot read that, so they become plain lists, thinned to every
second sample -- 768 points per flight is more than a 900-pixel chart can
resolve and doubles the download for nothing. And night/sonuclar/ carries the
per-frame records every run wrote, which is right for re-analysis and wrong for
a page that draws four charts.

    python space/hazirla.py     # then: python space/dagit.py
"""

import json
import shutil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "space" / "assets"
RES = ROOT / "results"
NIGHT = ROOT / "night" / "sonuclar"
ASSETS.mkdir(parents=True, exist_ok=True)

STRIDE = 2          # every second frame; charts cannot resolve more
ROUND = 2


def clean(a: np.ndarray, digits: int) -> list:
    """Rounded values with NaN as null.

    Frames where no position was produced are NaN, and json.dumps writes a bare
    NaN token that no JSON parser accepts -- the page died on it. null is both
    valid and what the chart wants: Plotly draws a gap, which is exactly what
    "no fix here" should look like.
    """
    out = np.round(np.asarray(a, dtype=float), digits)
    return [None if not np.isfinite(v) else v for v in out]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def flights() -> dict:
    """Per-flight curves, thinned and rounded, keyed by flight id."""
    out = {}
    for p in sorted(RES.glob("20_flight_[0-9][0-9].npz")):
        fid = p.stem.split("_")[-1]
        z = np.load(p)
        out[fid] = {
            "km": clean(z["dist"][::STRIDE] / 1000.0, 3),
            "err": clean(z["err"][::STRIDE], ROUND),
            "vo_err": clean(z["vo_err"][::STRIDE], ROUND),
            "inliers": clean(z["n_loftr"][::STRIDE], 0),
        }
    return out


def night() -> dict | None:
    taban, kopru = load(NIGHT / "01_taban.json"), load(NIGHT / "02_kopru_roma.json")
    dog, yasa = load(NIGHT / "03_dogrulama_1000.json"), load(NIGHT / "07_yasa_1000.json")
    kapi, tavan = load(NIGHT / "08_birlesik_1000.json"), load(NIGHT / "09_tavan_1000.json")
    if not all((taban, kopru, dog, yasa, kapi, tavan)):
        return None

    arms = {r["kol"]: r for r in taban}
    loftr_sobel = next((r for r in (load(NIGHT / "02_kopru_loftr.json") or [])
                        if r["temsil"] == "sobel"), None)
    roma_dog = next(r for r in kopru if r["temsil"] == "clahe+dog")
    rows = [
        ("LoFTR, raw thermal", arms["termal->uydu (LoFTR)"]["dogru_konum_orani"]),
        ("RoMa, raw thermal", arms["termal->uydu (RoMa)"]["dogru_konum_orani"]),
    ]
    if loftr_sobel:
        rows.append(("LoFTR, Sobel", loftr_sobel["dogru_konum_orani"]))
    rows.append(("RoMa, CLAHE+DoG", roma_dog["dogru_konum_orani"]))

    eski = kapi["kapilar"]["sonra (04'un kapisi)"]["ayrik"]
    taban_orani = sum(r["dogru"] for r in dog["kareler"]) / len(dog["kareler"])
    ops = [("tuned single-score gate", eski["kesinlik_medyan"],
            eski["duyarlilik_medyan"],
            eski["duyarlilik_medyan"] * taban_orani, 1.0)]
    for label, key in (("agreement only", "yok"),
                       ("agreement + top 50% of tiles", "%50"),
                       ("agreement + top 30% of tiles", "%30")):
        o = kapi["uzlasma"].get(key)
        if o:
            ops.append((label, o["kesinlik"], o["duyarlilik"],
                        o["dogru_kare_orani"], o["roma_cagrisi_kare_basina"]))

    hedef = tavan["her_iki_taraf"]["%30"]
    return {
        "arms": [{"ad": a, "dogru": v} for a, v in rows],
        "auc": [
            {"ad": "gradient orientation agreement",
             "v": dog["ozet"]["yon_uyumu"]["auc"], "ne": "after"},
            {"ad": "tile structure score (basemap only)",
             "v": yasa["ozet"][yasa["en_iyi_uydu"]]["auc"], "ne": "before"},
            {"ad": "inlier count", "v": dog["ozet"]["ic_nokta"]["auc"], "ne": "after"},
            {"ad": "edge density (basemap only)",
             "v": yasa["ozet"]["uydu_kenar_yogunlugu"]["auc"], "ne": "before"},
            {"ad": "mutual information",
             "v": max(dog["ozet"]["mi"]["auc"], 1 - dog["ozet"]["mi"]["auc"]),
             "ne": "after"},
        ],
        "decile": [round(x, 1) for x in yasa["decile"]["dogru_orani"]],
        "taban_orani": taban_orani,
        "ops": [{"ad": a, "kesinlik": p, "duyarlilik": r, "kare": f, "maliyet": c}
                for a, p, r, f, c in ops],
        "tavan": {"hedef_kare": hedef["basarisiz"],
                  "taban": taban_orani,
                  "tavan": taban_orani + hedef["basarisiz_kare_orani"]},
    }


def main() -> int:
    for src in (ROOT / "figures" / "demo.mp4",
                ROOT / "figures" / "31_gece_kanit.png"):
        if src.exists():
            shutil.copyfile(src, ASSETS / src.name)
            print(f"  {src.name}  ({src.stat().st_size / 1e6:.1f} MB)")
        else:
            print(f"  EKSIK: {src}")

    # Only the fields the page renders. Shipping the whole multiflight record
    # dragged in per-flight calibration values that are NaN on two flights and
    # that nothing on the page reads -- a payload should carry what is used.
    multi = load(RES / "20_multiflight.json") or {}
    data = {
        "ucuslar": flights(),
        "zorluk": load(RES / "21_flight_difficulty.json"),
        "multi": {k: {"kare": v.get("kare"), "km": v.get("km")}
                  for k, v in multi.items()},
        "gece": night(),
    }
    if data["gece"] is None:
        print("  NOT: gece verisi eksik, sayfa o bolumu gizleyecek")

    p = ASSETS / "data.json"
    # allow_nan=False turns a stray NaN into an exception here rather than
    # into a blank page in the browser.
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"),
                            allow_nan=False), encoding="utf-8")
    print(f"  data.json  ({p.stat().st_size / 1e6:.2f} MB, "
          f"{len(data['ucuslar'])} ucus)")
    print(f"\n-> {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

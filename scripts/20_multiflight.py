"""Faz 7 — cok ucuslu degerlendirme.

Projenin en buyuk zayifligi "tek ucus, tek bolge, tek mevsim"di. Bu betik ayni
kodu 8 farkli ucusta calistirip sonuclarin dagilimini cikariyor.

Ucuslar birbirinden ciddi bicimde farkli:
  ucus 01  406 m   817 kare      ucus 05  2313 m   473 kare  (sabit kanat!)
  ucus 02  406 m  1071 kare      ucus 06   834 m   344 kare
  ucus 03  466 m   768 kare      ucus 07   689 m    30 kare
  ucus 04  544 m   738 kare      ucus 08   551 m  1033 kare

Ucus 05'in irtifasi ucus 03'un bes kati. Hicbir sabit varsayilmiyor: yer
ornekleme araligi ve kamera montaj acisi HER UCUS icin ayri kestiriliyor,
kalibrasyon her zaman ilk %20'de yapilip kalan %80'de olculuyor.
"""
import sys
import json
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from src.flight import load_flight, MissingMetadata
from src.geo import SatelliteMap, haversine_m
from src.features import Dinov2Embedder
from src.matching import LoFTRMatcher, make_matcher
from src.localize import SingleFrameLocalizer
from src.particle_filter import PFConfig
from src.sequential import SequentialLocalizer
from src import pipeline as P

DATA = r"D:\GeoAnchorData\full"
CACHE = Path(r"D:\GeoAnchorData\cache_multi")
ROOT = Path(__file__).resolve().parents[1]
TAG_SUFFIX = ""
OUT = ROOT / "results" / "20_multiflight.json"


def set_out(tag):
    global OUT, TAG_SUFFIX
    TAG_SUFFIX = ("_" + tag) if tag else ""
    if tag:
        OUT = ROOT / "results" / ("20_multiflight_%s.json" % tag)


def load_done():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def do_flight(fid: str, emb: Dinov2Embedder, matcher: LoFTRMatcher) -> dict:
    t0 = time.time()
    flight = load_flight(DATA, fid)
    sat = SatelliteMap(flight.satellite_path)
    d = flight.df
    rec = {"ucus": fid, "kare": int(flight.n_frames),
           "irtifa_m": float(d["height"].mean()),
           "km": float(d["cum_dist_m"].iloc[-1] / 1000),
           "harita_px": [int(sat.width), int(sat.height)],
           "harita_gsd": float(sat.gsd)}

    # 1) IHA yer ornekleme araligi (bu ucusa ozel)
    gsd = P.estimate_drone_gsd(flight)
    rec["drone_gsd"] = float(gsd)
    if not np.isfinite(gsd):
        rec["durum"] = "olcek kestirilemedi"
        sat.close()
        return rec
    print("   olcek %.4f m/px, ayak izi ~%.0f m" % (gsd, gsd * 3976), flush=True)

    # 2) kuzey-yukari onbellek + karo veritabani + sorgu gommeleri
    q = P.cache_northup(flight, sat, gsd, CACHE)
    tlat, tlon, temb = P.build_tiles(sat, emb, CACHE, fid)
    qemb = P.embed_queries(q, emb, CACHE, fid)
    rec["karo"] = int(len(tlat))
    print("   %d karo, onbellek hazir (%.1f dk)" % (len(tlat), (time.time()-t0)/60),
          flush=True)

    # 3) boresight kalibrasyonu (ilk %20)
    att, before, after, n_cal = P.calibrate_boresight(flight, sat, q, matcher, gsd)
    rec.update({"boresight_egim": float(att.pitch_bias_deg),
                "boresight_yalpa": float(att.roll_bias_deg),
                "kal_kare": int(n_cal),
                "kal_once_m": float(before), "kal_sonra_m": float(after)})
    print("   boresight: egim %+.2f deg, yalpa %+.2f deg | kalibrasyon "
          "hatasi %.1f -> %.1f m" % (att.pitch_bias_deg, att.roll_bias_deg,
                                     before, after), flush=True)

    # 4) gorsel odometri
    dn, de = P.run_odometry(q, gsd, flight)
    gt_n, gt_e = d["north_m"].values, d["east_m"].values
    ok = np.isfinite(dn)
    rec["odo_tutma"] = float(ok.mean())
    # sadece odometriyle yorunge -> suruklenme
    nn = np.zeros(flight.n_frames); ee = np.zeros(flight.n_frames)
    nn[0], ee[0] = gt_n[0], gt_e[0]
    last = (0.0, 0.0)
    for i in range(flight.n_frames - 1):
        if np.isfinite(dn[i]):
            last = (dn[i], de[i])
        nn[i+1], ee[i+1] = nn[i] + last[0], ee[i] + last[1]
    vo_err = np.hypot(nn - gt_n, ee - gt_e)
    rec["odo_son_hata_m"] = float(vo_err[-1])
    rec["odo_suruklenme_yuzde"] = float(vo_err[-1] / max(1.0, d["cum_dist_m"].iloc[-1]) * 100)

    # 5) sirali fuzyon
    loc = SingleFrameLocalizer(sat, tlat, tlon, temb, matcher, att)
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    seq = SequentialLocalizer(sat, loc, att, lat0, lon0, pf_cfg=PFConfig(), seed=0)
    err = np.full(flight.n_frames, np.nan)
    nl = np.zeros(flight.n_frames)
    for i in range(flight.n_frames):
        r = d.iloc[i]
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        a = b = None
        if i > 0 and np.isfinite(dn[i-1]):
            a, b = float(dn[i-1]), float(de[i-1])
        res = seq.step(qg, qemb[i], float(r.Kappa), float(r.Omega),
                       float(r.height), float(r.Phi1), a, b)
        nl[i] = res.n_loftr
        if np.isfinite(res.north):
            err[i] = float(np.hypot(res.north - gt_n[i], res.east - gt_e[i]))

    e = err[np.isfinite(err)]
    if len(e) == 0:
        rec["durum"] = "sistem hic baslayamadi"
    else:
        rec.update({
            "durum": "tamam", "kapsama": float(len(e) / flight.n_frames),
            "medyan_m": float(np.median(e)), "ortalama_m": float(e.mean()),
            "p90_m": float(np.percentile(e, 90)), "max_m": float(e.max()),
            "basari_10m": float((e <= 10).mean() * len(e) / flight.n_frames),
            "basari_20m": float((e <= 20).mean() * len(e) / flight.n_frames),
            "loftr": float(nl.mean())})
    np.savez(ROOT / "results" / f"20_flight_{fid}{TAG_SUFFIX}.npz", err=err, n_loftr=nl,
             vo_err=vo_err, dist=d["cum_dist_m"].values)
    rec["sure_dk"] = float((time.time() - t0) / 60)
    sat.close()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matcher", default="loftr", choices=["loftr","roma"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--flights", default=None,
                    help="bosluklu liste; verilmezse hazir olanlarin hepsi")
    a = ap.parse_args()

    set_out(a.tag)
    ready = (a.flights.split() if a.flights else
             (ROOT / "data" / "ready_flights.txt").read_text().split())
    done = load_done()
    emb = Dinov2Embedder(img_size=448, mode="both")
    matcher = make_matcher(a.matcher) if a.matcher=="roma" else LoFTRMatcher(size=640)
    CACHE.mkdir(parents=True, exist_ok=True)

    for fid in ready:
        if fid in done and done[fid].get("durum") == "tamam":
            print("ucus %s: onceden yapilmis, atlandi" % fid, flush=True)
            continue
        print("\n=== UCUS %s ===" % fid, flush=True)
        try:
            done[fid] = do_flight(fid, emb, matcher)
        except MissingMetadata as ex:
            done[fid] = {"ucus": fid, "durum": "ustveri eksik",
                         "aciklama": str(ex)}
            print("   ATLANDI:", str(ex), flush=True)
        except Exception as ex:
            done[fid] = {"ucus": fid, "durum": "HATA: %s" % str(ex)[:150]}
            print("   HATA:", str(ex)[:200], flush=True)
        OUT.write_text(json.dumps(done, indent=2, ensure_ascii=False),
                       encoding="utf-8")
        r = done[fid]
        if r.get("durum") == "tamam":
            print("   SONUC: kapsama %%%.1f, medyan %.2f m, p90 %.2f m, "
                  "LoFTR/kare %.2f  (%.1f dk)" % (
                      r["kapsama"]*100, r["medyan_m"], r["p90_m"],
                      r["loftr"], r["sure_dk"]), flush=True)

    print("\n\n=== OZET ===")
    print("%-5s %7s %8s %7s %9s %8s %8s %8s" % (
        "ucus", "kare", "irtifa", "km", "kapsama", "medyan", "p90", "LoFTR"))
    print("-" * 70)
    meds = []
    for fid in ready:
        r = done.get(fid, {})
        if r.get("durum") != "tamam":
            print("%-5s  %s" % (fid, r.get("durum", "yapilmadi")))
            continue
        meds.append(r["medyan_m"])
        print("%-5s %7d %7.0fm %7.1f %8.1f%% %7.2fm %7.2fm %8.2f" % (
            fid, r["kare"], r["irtifa_m"], r["km"], r["kapsama"]*100,
            r["medyan_m"], r["p90_m"], r["loftr"]))
    if meds:
        print("-" * 70)
        print("%d ucus: medyan hatalarin medyani %.2f m (en iyi %.2f, en kotu %.2f)"
              % (len(meds), np.median(meds), min(meds), max(meds)))


if __name__ == "__main__":
    main()

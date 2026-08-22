"""RoMa'ya adil sans: esikleri ona gore yeniden ayarla.

Bulgu: RoMa YANLIS yere bakinca da eslesme uretiyor (medyan 341 ic nokta),
LoFTR ise sifir uretiyor. Yani LoFTR'in "40 ic nokta = burasi dogru yer"
kurali RoMa icin gecersiz — RoMa'da 341 zaten gurultu tabani.

Bu betik iki seyi olcer:
  1. Dogru/yanlis yer ayrimini en iyi yapan olcut nedir?
     (ham ic nokta sayisi mi, ic nokta ORANI mi, RoMa'nin kendi guveni mi)
  2. O olcutle ayirt etme ne kadar guvenilir? Ortusme varsa RoMa bu isi
     yapamaz demektir.

Ayrim guvenilir degilse RoMa daha guclu bir esleyici olsa bile bu gorevde
kullanilamaz: konumlandirma sistemi "bilmiyorum" diyebilmek zorundadir.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from src.flight import load_flight
from src.geo import SatelliteMap
from src.matching import LoFTRMatcher, RomaMatcher

DATA = r"D:\GeoAnchorData\full"
CACHE = Path(r"D:\GeoAnchorData\cache_multi")
ROOT = Path(__file__).resolve().parents[1]
N = 26


def stats(m, name, gray, fid="03"):
    flight = load_flight(DATA, fid)
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / f"northup_{fid}_640.npy", mmap_mode="r")
    rng = np.random.default_rng(7)
    rows = []
    idxs = np.linspace(0, flight.n_frames - 1, N).astype(int)
    for i in idxs:
        r = flight.df.iloc[i]
        qi = np.ascontiguousarray(q[i])
        a = cv2.cvtColor(qi, cv2.COLOR_RGB2GRAY) if gray else qi
        for etiket in ("dogru", "yanlis"):
            if etiket == "dogru":
                la, lo = float(r.lat), float(r.lon)
            else:
                la = sat.bounds.rb_lat + rng.random() * (sat.bounds.lt_lat - sat.bounds.rb_lat)
                lo = sat.bounds.lt_lon + rng.random() * (sat.bounds.rb_lon - sat.bounds.lt_lon)
            crop, _, _, _ = sat.crop_meters(la, lo, 400.0, 640)
            b = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY) if gray else crop
            pa, pb, cf = m.match(a, b)
            n_match = len(pa)
            n_in, ratio = 0, 0.0
            if n_match >= 30:
                H, mask = cv2.findHomography(pa.astype(np.float32),
                                             pb.astype(np.float32),
                                             cv2.USAC_MAGSAC, 4.0,
                                             maxIters=10_000, confidence=0.999)
                if mask is not None:
                    n_in = int(mask.sum())
                    ratio = n_in / max(1, n_match)
            conf = float(np.mean(cf)) if len(cf) else 0.0
            rows.append({"etiket": etiket, "ic_nokta": n_in, "oran": ratio,
                         "guven": conf, "eslesme": n_match})
    sat.close()
    return rows


def ayrim(rows, alan):
    d = np.array([r[alan] for r in rows if r["etiket"] == "dogru"], float)
    y = np.array([r[alan] for r in rows if r["etiket"] == "yanlis"], float)
    # en iyi esik: dogru/yanlis ayrimini en cok dogru yapan deger
    cand = np.unique(np.concatenate([d, y]))
    best_t, best_acc = None, 0.0
    for t in cand:
        acc = ((d >= t).sum() + (y < t).sum()) / (len(d) + len(y))
        if acc > best_acc:
            best_acc, best_t = acc, t
    return {"dogru_medyan": float(np.median(d)), "yanlis_medyan": float(np.median(y)),
            "dogru_min": float(d.min()), "yanlis_max": float(y.max()),
            "en_iyi_esik": float(best_t), "dogruluk": float(best_acc),
            "ortusme": bool(d.min() <= y.max())}


def main():
    out = {}
    for name, mk, gray in [("LoFTR", lambda: LoFTRMatcher(size=640), True),
                           ("RoMa", lambda: RomaMatcher(), False)]:
        print("=== %s ===" % name, flush=True)
        m = mk()
        rows = stats(m, name, gray)
        del m
        import torch
        torch.cuda.empty_cache()
        out[name] = {}
        for alan, baslik in [("ic_nokta", "ham ic nokta"),
                             ("oran", "ic nokta orani"),
                             ("guven", "esleyici guveni")]:
            a = ayrim(rows, alan)
            out[name][alan] = a
            print("  %-16s dogru medyan %9.3f | yanlis medyan %9.3f | "
                  "en iyi esik %9.3f -> dogruluk %%%.1f %s" % (
                      baslik, a["dogru_medyan"], a["yanlis_medyan"],
                      a["en_iyi_esik"], a["dogruluk"] * 100,
                      "(ORTUSME VAR)" if a["ortusme"] else "(temiz ayrim)"),
                  flush=True)
        print()

    (ROOT / "results" / "27_roma_threshold.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("results/27_roma_threshold.json yazildi")


if __name__ == "__main__":
    main()

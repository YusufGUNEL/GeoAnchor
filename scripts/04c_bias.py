"""Hata rastgele mi, yoksa sabit yönlü mü? Sabitse harita ile GPS arasında kayma var."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap, latlon_to_local_m, meters_per_degree
from src.matching import LoFTRMatcher

CACHE = Path(r"D:\GeoAnchorData\cache")
flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sat = SatelliteMap(flight.satellite_path)
q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
matcher = LoFTRMatcher(size=640)
src_px = int(round(400 / sat.gsd))
m_lat, m_lon = meters_per_degree(float(flight.df["lat"].mean()))

idxs = np.linspace(0, flight.n_frames - 1, 150).astype(int)
dn, de, keep = [], [], []
for i in idxs:
    r = flight.df.iloc[i]
    img, x0, y0 = sat.crop_around_latlon(float(r.lat), float(r.lon), src_px)
    crop = cv2.resize(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (640, 640), interpolation=cv2.INTER_AREA)
    qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
    pa, pb, _ = matcher.match(qg, crop)
    if len(pa) < 25: continue
    H, mask = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32),
                                 cv2.USAC_MAGSAC, 4.0, maxIters=10000, confidence=0.999)
    if H is None or mask.sum() < 25: continue
    p = H @ np.array([320.0, 320.0, 1.0]); u, v = p[0]/p[2], p[1]/p[2]
    k = src_px / 640
    plat, plon = sat.px_to_latlon(x0 + u*k, y0 + v*k)
    dn.append((float(plat) - float(r.lat)) * m_lat)     # kestirim - gerçek, kuzey (m)
    de.append((float(plon) - float(r.lon)) * m_lon)     # doğu (m)
    keep.append(i)

dn, de = np.array(dn), np.array(de)
r = np.hypot(dn, de)
print(f"n = {len(dn)}\n")
print("Hata bileşenleri (kestirim eksi gerçek):")
print(f"  kuzey : ortalama {dn.mean():+8.2f} m   medyan {np.median(dn):+8.2f} m   std {dn.std():7.2f} m")
print(f"  doğu  : ortalama {de.mean():+8.2f} m   medyan {np.median(de):+8.2f} m   std {de.std():7.2f} m")
print(f"  mesafe: medyan {np.median(r):.2f} m   ortalama {r.mean():.2f} m\n")

bias_n, bias_e = np.median(dn), np.median(de)
rc = np.hypot(dn - bias_n, de - bias_e)
print(f"Sabit kayma çıkarılırsa (kuzey {bias_n:+.2f} m, doğu {bias_e:+.2f} m):")
print(f"  medyan hata : {np.median(r):.2f} m -> {np.median(rc):.2f} m")
print(f"  ortalama    : {r.mean():.2f} m -> {rc.mean():.2f} m")
for t in [1,3,5,10,20]:
    print(f"  {t:>2} m içinde : {(r<=t).mean()*100:5.1f}%  ->  {(rc<=t).mean()*100:5.1f}%")

# kayma konuma göre değişiyor mu? (harita geneline yayılmış mı, yerel mi)
sub = flight.df.iloc[keep]
north, east = latlon_to_local_m(sub["lat"].values, sub["lon"].values,
                                float(flight.df["lat"].iloc[0]), float(flight.df["lon"].iloc[0]))
print(f"\nKayma konuma bağlı mı? (bağımsızsa korelasyon ~0)")
print(f"  kuzey hatası ~ konum kuzey : {np.corrcoef(north, dn)[0,1]:+.3f}")
print(f"  kuzey hatası ~ konum doğu  : {np.corrcoef(east,  dn)[0,1]:+.3f}")
print(f"  doğu  hatası ~ konum kuzey : {np.corrcoef(north, de)[0,1]:+.3f}")
print(f"  doğu  hatası ~ konum doğu  : {np.corrcoef(east,  de)[0,1]:+.3f}")
np.savez(Path(__file__).resolve().parents[1] / "results" / "04c_bias.npz",
         dn=dn, de=de, idx=np.array(keep), bias_n=bias_n, bias_e=bias_e)
sat.close()

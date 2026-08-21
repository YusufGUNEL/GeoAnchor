"""Hata gövde çerçevesinde sabit mi? İz-boyu / iz-dışı ayrıştırması.

İz-boyu (uçuş yönünde) sabit bir kayma = görüntü ile konum damgası arasında
zamanlama farkı. 18,7 m/sn hızda 1 saniyelik fark 18,7 m eder — ölçtüğümüz
hatanın tam mertebesi.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap, meters_per_degree
from src.matching import LoFTRMatcher

CACHE = Path(r"D:\GeoAnchorData\cache")
CROP_M, OUT = 400.0, 640
flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sat = SatelliteMap(flight.satellite_path)
q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
matcher = LoFTRMatcher(size=640)
m_lat, m_lon = meters_per_degree(float(flight.df["lat"].mean()))

idxs = np.linspace(0, flight.n_frames - 1, 150).astype(int)
rows = []
for i in idxs:
    r = flight.df.iloc[i]
    crop_rgb, x0, y0, mpp = sat.crop_meters(float(r.lat), float(r.lon), CROP_M, OUT)
    crop_g = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
    qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
    pa, pb, _ = matcher.match(qg, crop_g)
    if len(pa) < 25: continue
    H, mask = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32),
                                 cv2.USAC_MAGSAC, 4.0, maxIters=10000, confidence=0.999)
    if H is None or mask.sum() < 25: continue
    p = H @ np.array([320.,320.,1.]); u, v = p[0]/p[2], p[1]/p[2]
    mx, my = sat.out_px_to_map_px(u, v, x0, y0, CROP_M, OUT)
    plat, plon = sat.px_to_latlon(mx, my)
    dn = (float(plat) - float(r.lat)) * m_lat
    de = (float(plon) - float(r.lon)) * m_lon
    yaw = np.radians(float(r.Phi1))
    # ileri (yönelim) ve sağ birim vektörleri, (kuzey, doğu) bileşenleriyle
    f = np.array([np.cos(yaw), np.sin(yaw)])
    rt = np.array([-np.sin(yaw), np.cos(yaw)])
    err = np.array([dn, de])
    rows.append((i, err @ f, err @ rt, float(r.speed_ms), float(r.Phi1)))

a = np.array([r[1] for r in rows]); c = np.array([r[2] for r in rows])
sp = np.array([r[3] for r in rows]); yw = np.array([r[4] for r in rows])
print(f"n = {len(a)}\n")
print("Hata gövde çerçevesinde:")
print(f"  iz-boyu (ileri +) : ortalama {a.mean():+7.2f} m   medyan {np.median(a):+7.2f} m   std {a.std():6.2f} m")
print(f"  iz-dışı (sağ   +) : ortalama {c.mean():+7.2f} m   medyan {np.median(c):+7.2f} m   std {c.std():6.2f} m")
print(f"\n  toplam medyan hata: {np.median(np.hypot(a,c)):.2f} m")
print(f"  iz-boyu sabiti çıkarılırsa : {np.median(np.hypot(a-np.median(a), c)):.2f} m")
print(f"  her ikisi de çıkarılırsa   : {np.median(np.hypot(a-np.median(a), c-np.median(c))):.2f} m")

dt = np.median(a) / sp.mean()
print(f"\nZamanlama yorumu:")
print(f"  ortalama yer hızı        : {sp.mean():.2f} m/sn")
print(f"  iz-boyu kaymanın karşılığı: {dt:+.3f} saniye")
print(f"  iz-boyu kayma ~ hız korelasyonu: {np.corrcoef(sp, a)[0,1]:+.3f} "
      f"(zamanlama farkıysa pozitif olmalı)")

# iki uçuş yönünde ayrı ayrı
g1 = yw < 40; g2 = ~g1
print(f"\nUçuş yönüne göre (tarama deseninin iki kolu):")
print(f"  yönelim ~{yw[g1].mean():+.0f}° ({g1.sum()} kare): iz-boyu {np.median(a[g1]):+.2f} m, iz-dışı {np.median(c[g1]):+.2f} m")
print(f"  yönelim ~{yw[g2].mean():+.0f}° ({g2.sum()} kare): iz-boyu {np.median(a[g2]):+.2f} m, iz-dışı {np.median(c[g2]):+.2f} m")
np.savez(Path(__file__).resolve().parents[1]/"results"/"04h_body.npz",
         idx=np.array([r[0] for r in rows]), along=a, cross=c, speed=sp, yaw=yw)
sat.close()

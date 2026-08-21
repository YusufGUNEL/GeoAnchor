"""Yonelim sapmasi uydu eslemesinden okunabilir mi? (gercek konum kullanmadan)

Homografinin donme bileseni, kuzey-yukari yapilmis IHA karesi ile kuzey-yukari
uydu karosu arasindaki ARTIK aciyi verir. Bu artik aci sifir degilse, Phi1'in
kendisi o kadar sapmis demektir. Yani pusula hatasi haritadan olculebilir ve
hicbir GPS/gercek konum bilgisine ihtiyac duyulmaz.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap
from src.matching import LoFTRMatcher

CACHE = Path(r"D:\GeoAnchorData\cache")
flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sat = SatelliteMap(flight.satellite_path)
q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
matcher = LoFTRMatcher(size=640)
d = flight.df

idxs = np.linspace(0, flight.n_frames - 1, 90).astype(int)
rows = []
for i in idxs:
    r = d.iloc[i]
    crop_rgb, x0, y0, _ = sat.crop_meters(float(r.lat), float(r.lon), 400.0, 640)
    crop = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
    qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
    pa, pb, _ = matcher.match(qg, crop)
    if len(pa) < 40: continue
    M, mask = cv2.estimateAffinePartial2D(pa.astype(np.float32), pb.astype(np.float32),
                method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=10000, confidence=0.999)
    if M is None or mask.sum() < 40: continue
    ang = np.degrees(np.arctan2(M[1,0], M[0,0]))
    rows.append((float(r.Phi1), ang, int(mask.sum())))

p1 = np.array([r[0] for r in rows]); ang = np.array([r[1] for r in rows])
leg1 = p1 < 40; leg2 = ~leg1
print("Uydu eslemesinden okunan ARTIK donme acisi (gercek konum kullanilmadi):")
print("  leg1 (yaw~-40): medyan %+6.2f deg  std %5.2f  n=%d" % (np.median(ang[leg1]), ang[leg1].std(), leg1.sum()))
print("  leg2 (yaw~+122): medyan %+6.2f deg  std %5.2f  n=%d" % (np.median(ang[leg2]), ang[leg2].std(), leg2.sum()))
print()
print("Odometriden olculen yon sapmasi (gercek konumla, kiyas icin):")
print("  leg1 +1.65 deg   leg2 +7.22 deg")
print()
print("Ayni buyukluk ve ayni isaret cikiyorsa, pusula sapmasi HARITADAN")
print("olculebilir demektir; GPS'e ihtiyac yok.")
np.savez(Path(__file__).resolve().parents[1]/"results"/"06c_yaw_from_map.npz", phi1=p1, resid=ang)
sat.close()

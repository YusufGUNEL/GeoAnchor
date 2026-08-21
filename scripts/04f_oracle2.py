"""Metrik kare kırpma ile tavan ölçümü tekrar — en-boy düzeltmesi işe yaradı mı?"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m
from src.matching import LoFTRMatcher

CACHE = Path(r"D:\GeoAnchorData\cache")
flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sat = SatelliteMap(flight.satellite_path)
q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
matcher = LoFTRMatcher(size=640)
idxs = np.linspace(0, flight.n_frames - 1, 120).astype(int)

def evaluate(crop_m, model, isotropic):
    errs, inl, sc = [], [], []
    for i in idxs:
        r = flight.df.iloc[i]
        if isotropic:
            crop_rgb, x0, y0, _ = sat.crop_meters(float(r.lat), float(r.lon), crop_m, 640)
        else:
            src = int(round(crop_m / sat.gsd))
            arr, x0, y0 = sat.crop_around_latlon(float(r.lat), float(r.lon), src)
            crop_rgb = cv2.resize(arr, (640, 640), interpolation=cv2.INTER_AREA)
        crop = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        pa, pb, _ = matcher.match(qg, crop)
        if len(pa) < 25: continue
        pa32, pb32 = pa.astype(np.float32), pb.astype(np.float32)
        if model == "sim":
            M, mask = cv2.estimateAffinePartial2D(pa32, pb32, method=cv2.RANSAC,
                        ransacReprojThreshold=4.0, maxIters=10000, confidence=0.999)
            if M is None or mask.sum() < 25: continue
            u = M[0,0]*320+M[0,1]*320+M[0,2]; v = M[1,0]*320+M[1,1]*320+M[1,2]
            sc.append(float(np.hypot(M[0,0], M[1,0])))
        else:
            H, mask = cv2.findHomography(pa32, pb32, cv2.USAC_MAGSAC, 4.0,
                        maxIters=10000, confidence=0.999)
            if H is None or mask.sum() < 25: continue
            p = H @ np.array([320.,320.,1.]); u, v = p[0]/p[2], p[1]/p[2]
            sc.append(float(np.hypot(H[0,0], H[1,0])))
        if isotropic:
            mx, my = sat.out_px_to_map_px(u, v, x0, y0, crop_m, 640)
        else:
            k = int(round(crop_m/sat.gsd))/640
            mx, my = x0 + u*k, y0 + v*k
        plat, plon = sat.px_to_latlon(mx, my)
        errs.append(haversine_m(float(r.lat), float(r.lon), float(plat), float(plon)))
        inl.append(int(mask.sum()))
    return np.array(errs), np.array(inl), np.array(sc)

print(f"{'kırpma':>7} {'model':>6} {'metrik kare':>12} {'n':>4} {'medyan':>9} {'ort':>9} "
      f"{'%90':>9} {'<=5m':>7} {'<=10m':>7} {'<=20m':>7} {'iç nokta':>9}")
print("-" * 96)
for iso in [False, True]:
    for crop_m in [300, 400]:
        for model in ["sim", "homo"]:
            e, n_in, sc = evaluate(crop_m, model, iso)
            if len(e) == 0: continue
            print(f"{crop_m:>7} {model:>6} {str(iso):>12} {len(e):>4} {np.median(e):>8.2f}m "
                  f"{e.mean():>8.2f}m {np.percentile(e,90):>8.2f}m {(e<=5).mean()*100:>6.1f}% "
                  f"{(e<=10).mean()*100:>6.1f}% {(e<=20).mean()*100:>6.1f}% {np.median(n_in):>9.0f}")
    print()
sat.close()

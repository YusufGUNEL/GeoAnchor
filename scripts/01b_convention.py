"""Dönüş işareti ve açı kaynağını LoFTR ile kesinleştirir."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap
from src.matching import LoFTRMatcher, estimate_similarity, transform_scale_rot

DRONE_GSD, TILE_M = 0.1142, 300
flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sat = SatelliteMap(flight.satellite_path)
m = LoFTRMatcher(size=640)
side = int(TILE_M / sat.gsd)

from src.preprocess import drone_to_northup

print(f"{'kare':>5} {'kaynak':>8} {'işaret':>7} {'iç nokta':>9} {'ölçek':>7} {'artık açı':>10}")
print("-" * 56)
best = {}
for i in [40, 200, 440, 600]:
    r = flight.df.iloc[i]
    crop, _, _ = sat.crop_around_latlon(r.lat, r.lon, side)
    crop_g = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    drone = cv2.imread(str(flight.image_path(i)), cv2.IMREAD_GRAYSCALE)
    for src_name, yaw in [("Phi1", float(r.Phi1)), ("Phi2", float(r.Phi2))]:
        for sign in (-1.0, +1.0):
            nu = drone_to_northup(drone, yaw, DRONE_GSD, sat.gsd, TILE_M, yaw_sign=sign)
            pa, pb, cf = m.match(nu, crop_g)
            M, mask, n = estimate_similarity(pa, pb)
            if M is None:
                print(f"{i:>5} {src_name:>8} {sign:>+7.0f} {n:>9} {'--':>7} {'--':>10}")
                continue
            s, ang = transform_scale_rot(M)
            print(f"{i:>5} {src_name:>8} {sign:>+7.0f} {n:>9} {s:>7.3f} {ang:>10.2f}")
            best[(src_name, sign)] = best.get((src_name, sign), 0) + n
print("-" * 56)
for k, v in sorted(best.items(), key=lambda x: -x[1]):
    print(f"  {k[0]} işaret {k[1]:+.0f}: toplam iç nokta {v}")
sat.close()

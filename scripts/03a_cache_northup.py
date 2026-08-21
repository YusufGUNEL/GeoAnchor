"""İHA karelerinin kuzey-yukarı, uydu ölçeğine indirilmiş sürümlerini önbelleğe alır.

768 tane 3976x2652 JPEG'i her denemede yeniden okumak 131 sn yiyor. Bir kez
hazırlayıp diske memmap olarak yazıyoruz; sonraki tüm deneyler saniyeler içinde
başlıyor. Renk KORUNUYOR.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap
from src.preprocess import drone_to_northup

DATA_ROOT = r"D:\GeoAnchorData\raw"
CACHE = Path(r"D:\GeoAnchorData\cache"); CACHE.mkdir(exist_ok=True)
DRONE_GSD, TILE_M, OUT_PX = 0.1142, 300.0, 640

def main():
    flight = load_flight(DATA_ROOT, "03")
    sat = SatelliteMap(flight.satellite_path)
    n = flight.n_frames
    path = CACHE / f"northup_03_{OUT_PX}.npy"
    arr = np.lib.format.open_memmap(path, mode="w+", dtype=np.uint8,
                                    shape=(n, OUT_PX, OUT_PX, 3))
    t0 = time.time()
    for i in range(n):
        im = cv2.imread(str(flight.image_path(i)))          # BGR
        nu = drone_to_northup(im, float(flight.df["Phi1"].iloc[i]),
                              DRONE_GSD, sat.gsd, TILE_M,
                              yaw_sign=-1.0, out_px=OUT_PX)
        arr[i] = cv2.cvtColor(nu, cv2.COLOR_BGR2RGB)
        if (i + 1) % 128 == 0 or i == n - 1:
            el = time.time() - t0
            print(f"  {i+1}/{n}  {el:.0f} sn, ~{el/(i+1)*(n-i-1):.0f} sn kaldı")
    arr.flush()
    print(f"\nYazıldı: {path} ({path.stat().st_size/1e6:.0f} MB), "
          f"{TILE_M:.0f} m -> {OUT_PX} px = {TILE_M/OUT_PX:.3f} m/px")
    sat.close()

if __name__ == "__main__":
    main()

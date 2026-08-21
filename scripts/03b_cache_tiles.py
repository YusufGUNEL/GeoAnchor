"""Uydu karolarını önbelleğe alır ki gömme deneyleri hızlı dönsün."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap
from src.tiles import build_tile_grid

DATA_ROOT = r"D:\GeoAnchorData\raw"
CACHE = Path(r"D:\GeoAnchorData\cache"); CACHE.mkdir(exist_ok=True)
TILE_M, STRIDE_M, OUT_PX = 300.0, 150.0, 448

def main():
    flight = load_flight(DATA_ROOT, "03")
    sat = SatelliteMap(flight.satellite_path)
    x0, y0, lat, lon, tile_px, grid = build_tile_grid(sat, TILE_M, STRIDE_M)
    n = len(x0)
    print(f"{n} karo, kaynak {tile_px} px -> önbellek {OUT_PX} px")
    arr = np.lib.format.open_memmap(CACHE / f"tiles_03_{OUT_PX}.npy", mode="w+",
                                    dtype=np.uint8, shape=(n, OUT_PX, OUT_PX, 3))
    t0 = time.time()
    for i in range(n):
        t = sat.read_window(int(x0[i]), int(y0[i]), tile_px, tile_px)
        arr[i] = cv2.resize(t, (OUT_PX, OUT_PX), interpolation=cv2.INTER_AREA)
        if (i + 1) % 500 == 0 or i == n - 1:
            el = time.time() - t0
            print(f"  {i+1}/{n}  {el:.0f} sn, ~{el/(i+1)*(n-i-1):.0f} sn kaldı")
    arr.flush()
    np.savez(CACHE / "tilegrid_03.npz", x0=x0, y0=y0, lat=lat, lon=lon,
             tile_px=tile_px, grid=np.array(grid), tile_m=TILE_M, stride_m=STRIDE_M)
    print(f"Bitti: {(CACHE / f'tiles_03_{OUT_PX}.npy').stat().st_size/1e6:.0f} MB")
    sat.close()

if __name__ == "__main__":
    main()

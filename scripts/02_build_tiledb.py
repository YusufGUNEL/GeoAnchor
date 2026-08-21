"""Faz 1a — uydu haritasından karo gömme veritabanı üretir."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap
from src.features import Dinov2Embedder
from src.tiles import build_tile_grid, TileDB

DATA_ROOT = r"D:\GeoAnchorData\raw"
TILE_M, STRIDE_M = 300.0, 150.0
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

def main():
    flight = load_flight(DATA_ROOT, "03")
    sat = SatelliteMap(flight.satellite_path)
    x0, y0, lat, lon, tile_px, grid = build_tile_grid(sat, TILE_M, STRIDE_M)
    n = len(x0)
    print(f"Izgara {grid[0]} x {grid[1]} = {n} karo, kenar {tile_px} px ({TILE_M:.0f} m), "
          f"adım {STRIDE_M:.0f} m")

    emb_model = Dinov2Embedder(img_size=224, mode="both")
    embs = np.zeros((n, emb_model.dim), dtype=np.float32)

    BATCH = 32
    t0 = time.time()
    buf, buf_idx = [], []
    for i in range(n):
        buf.append(sat.read_window(int(x0[i]), int(y0[i]), tile_px, tile_px))
        buf_idx.append(i)
        if len(buf) == BATCH or i == n - 1:
            embs[buf_idx] = emb_model.embed(np.stack(buf), batch=BATCH)
            buf, buf_idx = [], []
            done = i + 1
            if done % 320 == 0 or done == n:
                el = time.time() - t0
                print(f"  {done}/{n}  ({done/n*100:.0f}%)  "
                      f"{el:.0f} sn geçti, ~{el/done*(n-done):.0f} sn kaldı")

    db = TileDB(lat=lat, lon=lon, x0=x0, y0=y0, tile_px=tile_px, tile_m=TILE_M,
                stride_m=STRIDE_M, emb=embs, grid_shape=grid)
    p = OUT / "tiledb_03.npz"
    db.save(p)
    print(f"\nKaydedildi: {p}  ({p.stat().st_size/1e6:.1f} MB)")
    print(f"Toplam süre: {(time.time()-t0)/60:.1f} dk")
    sat.close()

if __name__ == "__main__":
    main()

"""Uydu haritasının karo veritabanı: ızgara, gömme, en yakın komşu araması."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geo import SatelliteMap


@dataclass
class TileDB:
    """Karo merkezleri (coğrafi + piksel) ve gömme vektörleri."""
    lat: np.ndarray          # (N,)
    lon: np.ndarray          # (N,)
    x0: np.ndarray           # (N,) karo sol üst piksel
    y0: np.ndarray
    tile_px: int
    tile_m: float
    stride_m: float
    emb: np.ndarray          # (N, D) float32, L2-normalize
    grid_shape: tuple[int, int]

    def __len__(self):
        return len(self.lat)

    def search(self, q: np.ndarray, k: int = 10):
        """q: (D,) veya (B, D) sorgu vektörü -> (skorlar, indisler), skor azalan."""
        q = np.atleast_2d(q)
        sims = q @ self.emb.T                       # kosinüs (ikisi de normalize)
        idx = np.argpartition(-sims, kth=min(k, sims.shape[1] - 1), axis=1)[:, :k]
        rows = np.arange(len(q))[:, None]
        ord_ = np.argsort(-sims[rows, idx], axis=1)
        idx = idx[rows, ord_]
        return sims[rows, idx], idx

    def save(self, path: str | Path):
        np.savez_compressed(
            path, lat=self.lat, lon=self.lon, x0=self.x0, y0=self.y0,
            emb=self.emb, tile_px=self.tile_px, tile_m=self.tile_m,
            stride_m=self.stride_m, grid_shape=np.array(self.grid_shape))

    @staticmethod
    def load(path: str | Path) -> "TileDB":
        z = np.load(path)
        return TileDB(lat=z["lat"], lon=z["lon"], x0=z["x0"], y0=z["y0"],
                      tile_px=int(z["tile_px"]), tile_m=float(z["tile_m"]),
                      stride_m=float(z["stride_m"]), emb=z["emb"],
                      grid_shape=tuple(z["grid_shape"]))


def build_tile_grid(sat: SatelliteMap, tile_m: float, stride_m: float):
    """Harita üzerinde örtüşen karo ızgarası üretir."""
    tile_px = int(round(tile_m / sat.gsd))
    stride_px = int(round(stride_m / sat.gsd))
    xs = np.arange(0, sat.width - tile_px + 1, stride_px)
    ys = np.arange(0, sat.height - tile_px + 1, stride_px)
    gx, gy = np.meshgrid(xs, ys)
    x0 = gx.ravel()
    y0 = gy.ravel()
    lat, lon = sat.px_to_latlon(x0 + tile_px / 2, y0 + tile_px / 2)
    return x0, y0, np.asarray(lat), np.asarray(lon), tile_px, (len(ys), len(xs))

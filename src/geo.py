"""Coğrafi dönüşümler ve uydu haritası erişimi.

Uydu haritası 35092 x 24308 piksellik bir GeoTIFF (2,6 GB). Asla tamamı
belleğe alınmaz; rasterio pencere okumasıyla sadece gereken parça çekilir.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

EARTH_R = 6_371_008.8  # m, WGS84 ortalama yarıçap


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki coğrafi nokta arasındaki yüzey mesafesi (metre)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def haversine_m_array(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vektörleştirilmiş haversine (metre)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def meters_per_degree(lat: float) -> tuple[float, float]:
    """Verilen enlemde 1 derece enlem ve boylamın metre karşılığı."""
    lat_r = math.radians(lat)
    m_lat = 111_132.92 - 559.82 * math.cos(2 * lat_r) + 1.175 * math.cos(4 * lat_r)
    m_lon = 111_412.84 * math.cos(lat_r) - 93.5 * math.cos(3 * lat_r)
    return m_lat, m_lon


def latlon_to_local_m(lat, lon, lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    """Coğrafi koordinatı (lat0, lon0) merkezli yerel düzleme taşır.

    Döndürdüğü değerler: kuzey (m), doğu (m). Küçük bölgelerde (< 20 km)
    düzlem yaklaşımı birkaç santimetre hata yapar, bizim için fazlasıyla yeterli.
    """
    m_lat, m_lon = meters_per_degree(lat0)
    north = (np.asarray(lat, dtype=float) - lat0) * m_lat
    east = (np.asarray(lon, dtype=float) - lon0) * m_lon
    return north, east


def local_m_to_latlon(north, east, lat0: float, lon0: float):
    """latlon_to_local_m'in tersi."""
    m_lat, m_lon = meters_per_degree(lat0)
    lat = np.asarray(north, dtype=float) / m_lat + lat0
    lon = np.asarray(east, dtype=float) / m_lon + lon0
    return lat, lon


@dataclass
class MapBounds:
    lt_lat: float
    lt_lon: float
    rb_lat: float
    rb_lon: float


class SatelliteMap:
    """Coğrafi referanslı uydu ortofotosu.

    Piksel ile enlem/boylam arasında gidip gelmeyi ve istenen bir coğrafi
    noktanın etrafından kırpma almayı sağlar.
    """

    def __init__(self, tif_path: str | Path):
        self.path = Path(tif_path)
        self._ds = rasterio.open(self.path)
        self.width = self._ds.width
        self.height = self._ds.height
        b = self._ds.bounds
        self.bounds = MapBounds(lt_lat=b.top, lt_lon=b.left,
                                rb_lat=b.bottom, rb_lon=b.right)
        # derece / piksel
        self.deg_per_px_lon = (b.right - b.left) / self.width
        self.deg_per_px_lat = (b.top - b.bottom) / self.height
        self.center_lat = (b.top + b.bottom) / 2
        self.center_lon = (b.left + b.right) / 2
        m_lat, m_lon = meters_per_degree(self.center_lat)
        # yer örnekleme aralığı (metre / piksel)
        self.gsd_x = self.deg_per_px_lon * m_lon
        self.gsd_y = self.deg_per_px_lat * m_lat
        self.gsd = (self.gsd_x + self.gsd_y) / 2

    def close(self):
        self._ds.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- dönüşümler ---
    def latlon_to_px(self, lat, lon):
        """Enlem/boylam -> (x, y) piksel. Dizi de kabul eder."""
        x = (np.asarray(lon, dtype=float) - self.bounds.lt_lon) / self.deg_per_px_lon
        y = (self.bounds.lt_lat - np.asarray(lat, dtype=float)) / self.deg_per_px_lat
        return x, y

    def px_to_latlon(self, x, y):
        """(x, y) piksel -> enlem/boylam."""
        lon = self.bounds.lt_lon + np.asarray(x, dtype=float) * self.deg_per_px_lon
        lat = self.bounds.lt_lat - np.asarray(y, dtype=float) * self.deg_per_px_lat
        return lat, lon

    def contains(self, lat, lon) -> bool:
        return (self.bounds.rb_lat <= lat <= self.bounds.lt_lat
                and self.bounds.lt_lon <= lon <= self.bounds.rb_lon)

    # --- okuma ---
    def read_window(self, x0: int, y0: int, w: int, h: int) -> np.ndarray:
        """Piksel penceresi oku -> HxWx3 uint8. Harita dışı bölge siyah gelir."""
        win = Window(x0, y0, w, h)
        arr = self._ds.read(window=win, boundless=True, fill_value=0)
        return np.transpose(arr, (1, 2, 0))

    def crop_around_latlon(self, lat: float, lon: float, size_px: int) -> tuple[np.ndarray, int, int]:
        """Bir coğrafi noktanın etrafından size_px kenarlı kare kırpma.

        Döndürür: (görüntü, x0, y0) — x0/y0 kırpmanın haritadaki sol üst pikseli.
        """
        cx, cy = self.latlon_to_px(lat, lon)
        x0 = int(round(float(cx) - size_px / 2))
        y0 = int(round(float(cy) - size_px / 2))
        return self.read_window(x0, y0, size_px, size_px), x0, y0

    def crop_meters(self, lat: float, lon: float, size_m: float,
                    out_px: int) -> tuple[np.ndarray, float, float, float]:
        """Metrik olarak KARE bir kırpma döndürür (size_m x size_m gerçek metre).

        Harita EPSG:4326: pikseller derecede kare ama metrede değil. Bu enlemde
        yatay 0,252 m/px, düşey 0,298 m/px — %18 fark. Kaynak pencere bu yüzden
        piksel cinsinden dikdörtgen seçilip kare çıktıya yeniden örnekleniyor.
        Aksi halde İHA'nın izotropik karesiyle uydunun anizotropik karesi
        eşleşirken sistematik hata doğuyor.

        Döndürür: (görüntü out_px x out_px, x0, y0, gerçek_m_per_out_px)
        """
        w_px = size_m / self.gsd_x          # boylam yönünde kaç piksel
        h_px = size_m / self.gsd_y          # enlem yönünde kaç piksel
        cx, cy = self.latlon_to_px(lat, lon)
        x0 = float(cx) - w_px / 2
        y0 = float(cy) - h_px / 2
        arr = self.read_window(int(round(x0)), int(round(y0)),
                               int(round(w_px)), int(round(h_px)))
        import cv2
        out = cv2.resize(arr, (out_px, out_px), interpolation=cv2.INTER_AREA)
        return out, int(round(x0)), int(round(y0)), size_m / out_px

    def out_px_to_map_px(self, u: float, v: float, x0: int, y0: int,
                         size_m: float, out_px: int) -> tuple[float, float]:
        """crop_meters çıktısındaki (u, v) -> harita pikseli."""
        w_px = size_m / self.gsd_x
        h_px = size_m / self.gsd_y
        return x0 + u * (w_px / out_px), y0 + v * (h_px / out_px)

    def overview(self, max_side: int = 2000) -> np.ndarray:
        """Tüm haritanın küçültülmüş önizlemesi (şekiller için)."""
        scale = max(self.width, self.height) / max_side
        out_w = int(self.width / scale)
        out_h = int(self.height / scale)
        arr = self._ds.read(out_shape=(self._ds.count, out_h, out_w))
        return np.transpose(arr, (1, 2, 0))

    def __repr__(self):
        return (f"SatelliteMap({self.path.name}, {self.width}x{self.height} px, "
                f"GSD ~{self.gsd:.3f} m/px, "
                f"{self.bounds.lt_lat:.4f}..{self.bounds.rb_lat:.4f} N, "
                f"{self.bounds.lt_lon:.4f}..{self.bounds.rb_lon:.4f} E)")

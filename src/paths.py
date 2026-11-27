"""Veri klasörlerinin tek kaynağı.

Kök `GEOANCHOR_DATA` ortam değişkeninden okunur; yoksa D:\\GeoAnchorData.
"""
from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("GEOANCHOR_DATA", r"D:\GeoAnchorData"))
RAW = DATA_ROOT / "raw"                # UAV-VisLoc örnek kümesi (uçuş 03)
CACHE = DATA_ROOT / "cache"            # uçuş 03 önbellekleri
FULL = DATA_ROOT / "full"              # 10 uçuşluk tam küme
CACHE_MULTI = DATA_ROOT / "cache_multi"

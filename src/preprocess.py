"""İHA karesini uydu haritasıyla kıyaslanabilir hale getirme."""
from __future__ import annotations

import cv2
import numpy as np


def drone_to_northup(img: np.ndarray, yaw_deg: float, drone_gsd: float,
                     target_gsd: float, size_m: float,
                     yaw_sign: float = -1.0, out_px: int | None = None,
                     to_gray: bool = False) -> np.ndarray:
    """İHA karesini kuzey yukarı bakacak şekilde döndürüp uydu ölçeğine indirir.

    Döndürür: kenarı out_px (verilmezse size_m / target_gsd) piksel olan kare kırpma.
    Renk KORUNUR — uydu karoları renkli olduğu için gri tonlamaya çevirmek
    yapay bir alan farkı yaratır ve getirme başarımını çökertir (ölçüldü:
    R@1 %7,3 → renkli sürümle karşılaştır).
    yaw_sign konvansiyonu kalibrasyonla belirlenir (bkz scripts/01b_convention.py).
    """
    if to_gray and img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]
    full_px = size_m / target_gsd
    out_px = int(round(full_px)) if out_px is None else int(out_px)
    # İHA pikselinden çıktı pikseline; out_px küçültülmüşse ona göre ayarla
    scale = (drone_gsd / target_gsd) * (out_px / full_px)

    # tek adımda döndür + ölçekle + merkezle (iki kez örneklemekten iyi)
    M = cv2.getRotationMatrix2D((w / 2, h / 2), yaw_sign * yaw_deg, scale)
    M[0, 2] += out_px / 2 - w / 2
    M[1, 2] += out_px / 2 - h / 2
    return cv2.warpAffine(img, M, (out_px, out_px), flags=cv2.INTER_AREA,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def northup_center_offset_px(out_px: int) -> tuple[float, float]:
    """Kuzey-yukarı kırpmada İHA kare merkezinin piksel konumu."""
    return (out_px / 2.0, out_px / 2.0)

"""Görsel odometri: ardışık İHA kareleri arasındaki bağıl hareket.

Neden kolay tarafta: iki ardışık kare aynı kameradan, 7 saniye arayla, %79
örtüşmeyle geliyor. Mevsim/sensör farkı YOK. Bu yüzden uydu eşlemesinin aksine
klasik SIFT fazlasıyla yeterli — ölçüldü, medyan 254 iç nokta.

Önemli kolaylık: kareler zaten kuzey-yukarı döndürülmüş ve metrik ölçeğe
indirilmiş durumda (ataletsel ölçüm biriminden gelen yönelim ve altimetreden
gelen irtifa ile — ikisi de GPS'siz çalışır). Dolayısıyla iki kare arasındaki
dönüşüm neredeyse saf ötelemedir ve doğrudan metre cinsinden okunur.

Sürüklenme kaçınılmazdır: her adımın küçük hatası toplanır. Bu bir kusur değil,
Faz 3'ün varlık sebebidir.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class OdoStep:
    """İki kare arasındaki bağıl hareket kestirimi."""
    ok: bool
    d_east_m: float = float("nan")
    d_north_m: float = float("nan")
    inliers: int = 0
    resid_rot_deg: float = float("nan")
    resid_scale: float = float("nan")


class VisualOdometry:
    """Kuzey-yukarı, metrik ölçekli kare çiftlerinden öteleme kestirir."""

    def __init__(self, m_per_px: float, nfeatures: int = 4000,
                 ratio: float = 0.75, ransac_thr: float = 3.0,
                 min_inliers: int = 30):
        self.m_per_px = m_per_px
        self.sift = cv2.SIFT_create(nfeatures=nfeatures)
        self.bf = cv2.BFMatcher()
        self.ratio = ratio
        self.ransac_thr = ransac_thr
        self.min_inliers = min_inliers

    def step(self, prev_gray: np.ndarray, curr_gray: np.ndarray) -> OdoStep:
        """prev -> curr hareketi. Döndürülen değer İHA'nın yer üstündeki yer değiştirmesi."""
        k1, d1 = self.sift.detectAndCompute(prev_gray, None)
        k2, d2 = self.sift.detectAndCompute(curr_gray, None)
        if d1 is None or d2 is None or len(k1) < 10 or len(k2) < 10:
            return OdoStep(ok=False)
        raw = self.bf.knnMatch(d1, d2, k=2)
        good = [m for m, n in raw if m.distance < self.ratio * n.distance]
        if len(good) < self.min_inliers:
            return OdoStep(ok=False, inliers=len(good))
        p1 = np.float32([k1[m.queryIdx].pt for m in good])
        p2 = np.float32([k2[m.trainIdx].pt for m in good])
        M, mask = cv2.estimateAffinePartial2D(
            p1, p2, method=cv2.RANSAC, ransacReprojThreshold=self.ransac_thr,
            maxIters=10_000, confidence=0.999, refineIters=20)
        if M is None or mask is None:
            return OdoStep(ok=False)
        n = int(mask.sum())
        if n < self.min_inliers:
            return OdoStep(ok=False, inliers=n)

        # M, prev'deki noktayı curr'a taşır. Sahne curr'da -M[:,2] kadar kaymışsa
        # kamera +M[:,2] yönünün TERSİNE gitmiştir.
        dx_px, dy_px = float(M[0, 2]), float(M[1, 2])
        # görüntü ekseni: x sağa = doğu, y aşağı = güney (kuzey-yukarı kırpma)
        d_east = -dx_px * self.m_per_px
        d_north = +dy_px * self.m_per_px
        rot = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
        sc = float(np.hypot(M[0, 0], M[1, 0]))
        return OdoStep(ok=True, d_east_m=d_east, d_north_m=d_north,
                       inliers=n, resid_rot_deg=rot, resid_scale=sc)


def integrate(steps: list[OdoStep], start_north: float = 0.0,
              start_east: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Adımları toplayıp yörünge üretir. Tutmayan adımda son hız sürdürülür."""
    n = len(steps) + 1
    north = np.zeros(n)
    east = np.zeros(n)
    north[0], east[0] = start_north, start_east
    last = (0.0, 0.0)
    for i, s in enumerate(steps):
        if s.ok:
            last = (s.d_north_m, s.d_east_m)
        north[i + 1] = north[i] + last[0]
        east[i + 1] = east[i] + last[1]
    return north, east

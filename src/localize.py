"""Tek kare mutlak konumlandırma: getirme -> LoFTR doğrulama -> duruş düzeltmesi."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .geo import SatelliteMap, haversine_m, meters_per_degree
from .geometry import AttitudeModel
from .matching import LoFTRMatcher


@dataclass
class Fix:
    """Tek karelik konum kestirimi."""
    ok: bool = False
    lat: float = float("nan")
    lon: float = float("nan")
    inliers: int = 0
    n_matches: int = 0
    scale: float = float("nan")
    angle: float = float("nan")
    cand_rank: int = -1
    n_tried: int = 0
    cand_scores: list = field(default_factory=list)


def suppress_neighbors(lat, lon, order, min_sep_m: float, max_out: int) -> list[int]:
    """Sıralı adaylardan birbirine çok yakın olanları eler.

    Karolar %50 örtüştüğü için en iyi 40 aday çoğunlukla aynı noktanın
    komşularıdır — bu tek bir tahmin demektir. Ayırınca gerçek alternatifler
    elde edilir ve yanlış bölgeye düşen kareler kurtarılabilir.
    """
    keep: list[int] = []
    for i in order:
        i = int(i)
        if all(haversine_m(lat[i], lon[i], lat[j], lon[j]) >= min_sep_m for j in keep):
            keep.append(i)
            if len(keep) >= max_out:
                break
    return keep


class SingleFrameLocalizer:
    """Bir İHA karesini haritanın TAMAMINDA arar (öncül bilgi yok).

    Boru hattı:
      1. küresel getirme (ucuz, DINOv2)  -> aday bölgeler
      2. LoFTR + homografi (pahalı)      -> hangi aday doğru + tam konum
      3. duruş düzeltmesi                -> görüntü merkezi yerine İHA konumu
    """

    def __init__(self, sat: SatelliteMap, tile_lat, tile_lon, tile_emb,
                 matcher: LoFTRMatcher, attitude: AttitudeModel,
                 crop_m: float = 400.0, crop_px: int = 640,
                 min_inliers: int = 40, early_exit: int = 200,
                 max_cands: int = 8, cand_sep_m: float = 200.0,
                 topk_pool: int = 40, ransac_thr: float = 4.0):
        self.sat = sat
        self.tile_lat, self.tile_lon, self.tile_emb = tile_lat, tile_lon, tile_emb
        self.matcher = matcher
        self.att = attitude
        self.crop_m, self.crop_px = crop_m, crop_px
        self.min_inliers, self.early_exit = min_inliers, early_exit
        self.max_cands, self.cand_sep_m = max_cands, cand_sep_m
        self.topk_pool, self.ransac_thr = topk_pool, ransac_thr
        self.m_lat, self.m_lon = meters_per_degree(sat.center_lat)

    def match_at(self, query_gray: np.ndarray, lat: float, lon: float,
                 blur_sigma: float = 0.0, auto_blur: bool = False):
        """Sorguyu verilen merkezdeki uydu kırpmasıyla eşler.

        Döndürür: (lat, lon, ic_nokta, eslesme_sayisi, olcek, aci) — görüntü
        merkezinin YER noktası (henüz duruş düzeltmesi yapılmamış).
        "aci", kuzey-yukarı yapılmış İHA karesi ile kuzey-yukarı uydu karosu
        arasındaki ARTIK dönmedir: sıfır değilse yönelim açısının kendisi o
        kadar sapmış demektir. Bu, pusula hatasını gerçek konum bilgisi
        OLMADAN ölçmeyi sağlar (bkz scripts/06c_yaw_from_map.py).
        """
        crop_rgb, x0, y0, _ = self.sat.crop_meters(lat, lon, self.crop_m, self.crop_px)
        crop = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
        if auto_blur:
            # ALAN ESITLEME, referansi uydudan alarak.
            # Bulanikligi "mutlak" olcmek mumkun degil: hic net kare gormemis
            # bir kamera ne kadar bulanik oldugunu bilemez. Ama elimizde her
            # karede hazir bir NET referans var — uydu karosunun kendisi.
            # Ikisi de ayni yeri ayni metre/piksel olceginde gosterdigi icin
            # aradaki keskinlik farki dogrudan bulanikligin olcusudur.
            from .quality import BlurCalibration, sharpness, match_blur
            cal = BlurCalibration()
            cal.fit(crop)
            s_sat = sharpness(crop)
            if s_sat > 0:
                blur_sigma = cal.sigma_for(sharpness(query_gray) / s_sat)
        if blur_sigma > 0.15:
            from .quality import match_blur
            crop = match_blur(crop, blur_sigma)
        pa, pb, _ = self.matcher.match(query_gray, crop)
        if len(pa) < self.min_inliers:
            return None, None, 0, len(pa), float("nan"), float("nan")
        H, mask = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32),
                                     cv2.USAC_MAGSAC, self.ransac_thr,
                                     maxIters=10_000, confidence=0.999)
        if H is None or mask is None:
            return None, None, 0, len(pa), float("nan"), float("nan")
        n = int(mask.sum())
        if n < self.min_inliers:
            return None, None, n, len(pa), float("nan"), float("nan")
        c = self.crop_px / 2.0
        p = H @ np.array([c, c, 1.0])
        if abs(p[2]) < 1e-9:
            return None, None, n, len(pa), float("nan"), float("nan")
        u, v = p[0] / p[2], p[1] / p[2]
        # kestirilen nokta kırpmanın çok dışına düşerse eşleme saçmalamıştır
        lo_b, hi_b = -self.crop_px * 0.5, self.crop_px * 1.5
        if not (lo_b < u < hi_b and lo_b < v < hi_b):
            return None, None, n, len(pa), float("nan"), float("nan")
        mx, my = self.sat.out_px_to_map_px(u, v, x0, y0, self.crop_m, self.crop_px)
        plat, plon = self.sat.px_to_latlon(mx, my)
        s = float(np.hypot(H[0, 0], H[1, 0]))
        ang = float(np.degrees(np.arctan2(H[1, 0], H[0, 0])))
        return float(plat), float(plon), n, len(pa), s, ang

    def apply_attitude(self, lat, lon, pitch, roll, height, yaw):
        """Görüntü merkezinin yer noktasından İHA konumuna geç."""
        la, lo = self.att.correct(lat, lon, pitch, roll, height, yaw,
                                  self.m_lat, self.m_lon)
        return float(la), float(lo)

    def localize(self, query_gray: np.ndarray, query_emb: np.ndarray,
                 pitch: float, roll: float, height: float, yaw: float) -> Fix:
        """Haritanın tamamında arar ve düzeltilmiş konumu döndürür."""
        sims = query_emb @ self.tile_emb.T
        order = np.argsort(-sims)[:self.topk_pool]
        cands = suppress_neighbors(self.tile_lat, self.tile_lon, order,
                                   self.cand_sep_m, self.max_cands)
        best = Fix(n_tried=0)
        for rank, ci in enumerate(cands):
            la, lo, n, nm, s, ang = self.match_at(query_gray,
                                                  float(self.tile_lat[ci]),
                                                  float(self.tile_lon[ci]))
            best.cand_scores.append(n)
            best.n_tried = rank + 1
            if la is not None and n > best.inliers:
                clat, clon = self.apply_attitude(la, lo, pitch, roll, height, yaw)
                best.ok, best.lat, best.lon = True, clat, clon
                best.inliers, best.n_matches, best.scale = n, nm, s
                best.angle = ang
                best.cand_rank = rank
            if best.ok and best.inliers >= self.early_exit:
                break
        return best

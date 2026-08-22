"""Görüntü eşleme: LoFTR (öğrenilmiş, yoğun) + RANSAC benzerlik dönüşümü.

Neden LoFTR: uydu görüntüsü ile İHA kaydı arasında mevsim, güneş açısı ve
sensör farkı var. SIFT bu farkı aşamıyor (deneyle görüldü: 12-34 iç nokta).
LoFTR dedektörsüz çalışır ve görünüm değişimine belirgin biçimde dayanıklıdır.
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
import kornia.feature as KF


class LoFTRMatcher:
    """LoFTR sarmalayıcı. Girdi gri tonlamalı uint8, çıktı eşleşen nokta çiftleri."""

    def __init__(self, size: int = 640, device: str = "cuda", conf_thr: float = 0.5):
        self.size = size
        self.device = device
        self.conf_thr = conf_thr
        self.model = KF.LoFTR(pretrained="outdoor").eval().to(device)

    @torch.no_grad()
    def match(self, img_a: np.ndarray, img_b: np.ndarray):
        """İki gri görüntüyü eşler.

        Döndürür: (pts_a, pts_b, conf) — noktalar GİRDİ görüntülerinin kendi
        piksel koordinatlarında (LoFTR için yapılan yeniden boyutlandırma geri alınır).
        """
        ha, wa = img_a.shape[:2]
        hb, wb = img_b.shape[:2]
        a = cv2.resize(img_a, (self.size, self.size))
        b = cv2.resize(img_b, (self.size, self.size))

        ta = torch.from_numpy(a)[None, None].float().to(self.device) / 255.0
        tb = torch.from_numpy(b)[None, None].float().to(self.device) / 255.0
        out = self.model({"image0": ta, "image1": tb})

        pa = out["keypoints0"].cpu().numpy()
        pb = out["keypoints1"].cpu().numpy()
        cf = out["confidence"].cpu().numpy()

        keep = cf >= self.conf_thr
        pa, pb, cf = pa[keep], pb[keep], cf[keep]

        # LoFTR ölçeğinden girdi ölçeğine geri al
        pa = pa * np.array([wa / self.size, ha / self.size])
        pb = pb * np.array([wb / self.size, hb / self.size])
        return pa, pb, cf


def estimate_similarity(pts_a: np.ndarray, pts_b: np.ndarray,
                        thr: float = 4.0, min_inliers: int = 15):
    """A'dan B'ye benzerlik dönüşümü (ölçek + dönme + öteleme) kestirir.

    Döndürür: (M 2x3 veya None, iç nokta maskesi, iç nokta sayısı)
    """
    if len(pts_a) < min_inliers:
        return None, None, 0
    M, mask = cv2.estimateAffinePartial2D(
        pts_a.astype(np.float32), pts_b.astype(np.float32),
        method=cv2.RANSAC, ransacReprojThreshold=thr,
        maxIters=10_000, confidence=0.999, refineIters=20)
    if M is None or mask is None:
        return None, None, 0
    n = int(mask.sum())
    if n < min_inliers:
        return M, mask, n
    return M, mask, n


def transform_scale_rot(M: np.ndarray) -> tuple[float, float]:
    """Benzerlik matrisinden ölçek ve dönme açısını (derece) çıkarır."""
    s = float(np.hypot(M[0, 0], M[1, 0]))
    ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    return s, ang


def apply_M(M: np.ndarray, pt: tuple[float, float]) -> tuple[float, float]:
    """Tek bir noktayı 2x3 dönüşümle taşır."""
    x, y = pt
    return (float(M[0, 0] * x + M[0, 1] * y + M[0, 2]),
            float(M[1, 0] * x + M[1, 1] * y + M[1, 2]))


class RomaMatcher:
    """RoMa yogun esleyici — LoFTRMatcher ile ayni arayuz.

    NEDEN EKLENDI: dokuz ucusluk degerlendirme, basarimi belirleyen seyin
    esleme kalitesi oldugunu gosterdi (bkz scripts/21_why_flights_differ.py).
    Uc ucusta LoFTR karelerin sadece %12-42'sinde tutuyordu; RoMa ayni
    karelerde %96-100'e cikariyor:

        ucus   LoFTR ic nokta / tutma     RoMa ic nokta / tutma
        03            468 / %100              4342 / %100
        01            118 / % 75              1766 / % 96
        05             65 / % 54              1658 / %100
        02             12 / % 42               704 / %100
        08             14 / % 29              2935 / %100
        10              0 / % 12               160 / % 96

    Bedeli hiz: kare basina ~1,6 sn (LoFTR ~0,3 sn). VRAM 2,7 GB, yani 4 GB'lik
    kartta calisiyor.

    upsample_preds ACIK olmali: kapaliyken eslesme sayisi yuksek ama konum
    hassasiyeti dusuyor (ucus 08'de 50,3 m'ye karsi 24,8 m).
    """

    def __init__(self, coarse: int = 280, upsample: int = 448,
                 n_sample: int = 5000, device: str = "cuda"):
        from romatch import roma_outdoor
        self.model = roma_outdoor(device=device, coarse_res=coarse,
                                  upsample_res=upsample)
        self.model.upsample_preds = True
        self.n_sample = n_sample
        self.device = device
        self.size = upsample

    @torch.no_grad()
    def match(self, img_a: np.ndarray, img_b: np.ndarray):
        """LoFTRMatcher.match ile ayni sozlesme: (pts_a, pts_b, guven)."""
        from PIL import Image
        ha, wa = img_a.shape[:2]
        hb, wb = img_b.shape[:2]
        a = cv2.cvtColor(img_a, cv2.COLOR_GRAY2RGB) if img_a.ndim == 2 else img_a
        b = cv2.cvtColor(img_b, cv2.COLOR_GRAY2RGB) if img_b.ndim == 2 else img_b
        warp, cert = self.model.match(Image.fromarray(a), Image.fromarray(b),
                                      device=self.device)
        matches, c = self.model.sample(warp, cert, num=self.n_sample)
        kpa, kpb = self.model.to_pixel_coordinates(matches, ha, wa, hb, wb)
        c = c.cpu().numpy() if hasattr(c, "cpu") else np.asarray(c)
        return kpa.cpu().numpy(), kpb.cpu().numpy(), c


def make_matcher(name: str = "loftr", **kw):
    """Esleyici secimi: 'loftr' (hizli) veya 'roma' (dayanikli)."""
    if name.lower() == "roma":
        return RomaMatcher(**kw)
    return LoFTRMatcher(**kw)

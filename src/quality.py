"""Kare kalitesi: bulanıklık tespiti ve alan eşitleme.

NEDEN GEREKLİ (ölçüldü, bkz results/08_robustness.json):
Ağır titreşim bulanıklığında sistem çöküyordu — medyan hata 6,6 m'den
58,3 m'ye fırlıyor, karelerin sadece %2,7'si 10 m içinde kalıyordu.

Sebep göründüğü gibi "eşleme tutmuyor" değil. Tam tersi: bulanık kare
**yanlış** eşleşme üretiyor ve süzgece güvenle veriliyor. Yanlış ölçüm, hiç
ölçüm olmamasından kötüdür — süzgeç ölçümsüz kareyi odometriyle geçiştirebilir,
ama yanlış ölçüm onu yoldan çıkarır.

İKİ AYRI DURUM, İKİ AYRI ÇARE — ve bunları karıştırmamak önemli:

  A) ARADA BİR bulanık kare (gerçekçi olan: rüzgâr darbesi, ani manevra).
     Çare: o kareyi eşlemeye hiç sokma, odometriyle geç. Bir sonraki net
     karede zaten düzelir.

  B) HER KARE bulanık (kötü kamera, sürekli titreşim).
     Çare A burada İŞE YARAMAZ — hepsini atarsan sistem tamamen odometriye
     kalır ve sürüklenir, yani daha kötü olur. Bunun çaresi **alan eşitleme**:
     uydu karosunu da aynı kadar bulanıklaştır. Eşleme, iki taraf birbirine
     benzediğinde çalışır.

Bu yüzden kapı MUTLAK bir eşikle değil, KOMŞU KARELERE göre çalışıyor: kare
son karelerden belirgin biçimde bulanıksa atlanır; her şey aynı ölçüde
bulanıksa atlanmaz, bunun yerine alan eşitleme devreye girer.
"""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np


def sharpness(img: np.ndarray) -> float:
    """Laplace varyansı — keskin görüntüde yüksek, bulanıkta düşük.

    Klasik ve ucuz ölçüt: kenarlar ne kadar belirginse ikinci türevin varyansı
    o kadar büyük olur. Tek kare, tek geçiş, referans gerekmez.
    """
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def match_blur(img: np.ndarray, sigma: float) -> np.ndarray:
    """Uydu kırpmasını verilen yarıçapla yumuşat (alan eşitleme)."""
    if sigma <= 0.15:
        return img
    k = int(2 * round(3 * sigma) + 1)
    return cv2.GaussianBlur(img, (k, k), sigma)


class BlurCalibration:
    """Keskinlik oranını Gauss yarıçapına çeviren çizelge.

    Formül uydurmak yerine ölçüyoruz: net bir kareyi bilinen yarıçaplarla
    bulanıklaştırıp keskinliğin nasıl düştüğünü kaydediyoruz. Sonra ters
    yönde okuyoruz — "bu kadar keskinlik kaybı, şu kadar bulanıklığa denk".
    Kamera ve sahne değişse de kendini yeniden kalibre eder.
    """

    SIGMAS = np.array([0.0, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 5.0, 7.0])

    def __init__(self):
        self.ratios: np.ndarray | None = None

    def fit(self, sharp_img: np.ndarray):
        if sharp_img.ndim == 3:
            sharp_img = cv2.cvtColor(sharp_img, cv2.COLOR_RGB2GRAY)
        base = sharpness(sharp_img)
        if base <= 0:
            return
        vals = []
        for s in self.SIGMAS:
            v = sharpness(match_blur(sharp_img, float(s))) if s > 0 else base
            vals.append(v / base)
        self.ratios = np.array(vals)

    def sigma_for(self, ratio: float) -> float:
        """Gözlenen keskinlik oranına karşılık gelen yarıçap."""
        if self.ratios is None or not np.isfinite(ratio):
            return 0.0
        r = float(np.clip(ratio, self.ratios[-1], 1.0))
        # ratios azalan; ters cevirip enterpolasyon
        return float(np.interp(r, self.ratios[::-1], self.SIGMAS[::-1]))


class SharpnessGate:
    """Bulanık kareyi eşlemeye sokmama kapısı + alan eşitleme yarıçapı.

    Kapı KOMŞU KARELERE göre çalışır (yukarıdaki A/B ayrımı). Yarıçap ise
    uçuşun gördüğü en net karelere göre hesaplanır, çünkü "bu kamera ne kadar
    net görebiliyor" sorusunun cevabı odur.
    """

    def __init__(self, window: int = 20, rel_thresh: float = 0.40,
                 warmup: int = 12, enabled: bool = True,
                 blur_matching: bool = True):
        self.window = window
        self.rel_thresh = rel_thresh
        self.warmup = warmup
        self.enabled = enabled
        self.blur_matching = blur_matching
        self.recent: deque[float] = deque(maxlen=window)
        self.best: list[float] = []          # gorulen en net kareler
        self.calib = BlurCalibration()
        self._calibrated = False

    def _peak(self) -> float:
        """Bu kameranın ulaşabildiği keskinlik (yüksek yüzdelik)."""
        if not self.best:
            return float("nan")
        return float(np.percentile(self.best, 90))

    def check(self, img: np.ndarray):
        """Döndürür: (eşlemeye_değer_mi, keskinlik, eşitleme_için_sigma)."""
        s = sharpness(img)
        self.best.append(s)
        if len(self.best) > 200:
            self.best = self.best[-200:]

        # ilk net kareyle bulanıklık çizelgesini kalibre et
        if not self._calibrated and len(self.recent) >= self.warmup:
            if s >= np.median(self.recent):
                self.calib.fit(img)
                self._calibrated = True

        ok = True
        if self.enabled and len(self.recent) >= self.warmup:
            ref_local = float(np.median(self.recent))
            if ref_local > 0 and s < self.rel_thresh * ref_local:
                ok = False

        sigma = 0.0
        if self.blur_matching:
            peak = self._peak()
            if np.isfinite(peak) and peak > 0:
                sigma = self.calib.sigma_for(s / peak)

        self.recent.append(s)
        return ok, s, sigma

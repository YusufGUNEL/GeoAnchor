"""Faz 4 — gerçek harekât koşullarını taklit eden görüntü bozulmaları.

Laboratuvar verisi temizdir. Gerçek uçuşta kamera sis görür, gece uçar,
titreşimden bulanıklaşır, bant genişliği için görüntü sıkıştırılır, bulut
sahneyi kapatır. Bir seyrüsefer sisteminin değeri temiz karede ne yaptığıyla
değil, bunlar altında ayakta kalıp kalmadığıyla ölçülür.

Her bozulma tek bir "şiddet" parametresiyle (0 = temiz, 1 = ağır) ölçeklenir,
böylece dayanıklılık eğrisi çizilebilir.
"""
from __future__ import annotations

import cv2
import numpy as np


def motion_blur(img: np.ndarray, severity: float, rng=None) -> np.ndarray:
    """Titreşim / hızlı hareket bulanıklığı."""
    if severity <= 0:
        return img
    k = int(3 + severity * 24) | 1
    ang = 0.0 if rng is None else rng.uniform(0, 180)
    kern = np.zeros((k, k), np.float32)
    kern[k // 2, :] = 1.0
    M = cv2.getRotationMatrix2D((k / 2 - 0.5, k / 2 - 0.5), ang, 1.0)
    kern = cv2.warpAffine(kern, M, (k, k))
    s = kern.sum()
    if s > 0:
        kern /= s
    return cv2.filter2D(img, -1, kern)


def fog(img: np.ndarray, severity: float, rng=None) -> np.ndarray:
    """Sis / pus: karşıtlık düşer, parlaklık artar."""
    if severity <= 0:
        return img
    a = 1.0 - 0.75 * severity          # karşıtlık çarpanı
    veil = 190.0 * severity
    return np.clip(img.astype(np.float32) * a + veil * (1 - a) + veil * 0.35,
                   0, 255).astype(np.uint8)


def low_light(img: np.ndarray, severity: float, rng=None) -> np.ndarray:
    """Alacakaranlık / gece: kararma + sensör gürültüsü."""
    if severity <= 0:
        return img
    gain = 1.0 - 0.85 * severity
    out = img.astype(np.float32) * gain
    noise_sd = 2.0 + 18.0 * severity
    if rng is not None:
        out += rng.normal(0.0, noise_sd, out.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def jpeg(img: np.ndarray, severity: float, rng=None) -> np.ndarray:
    """Bant genişliği için ağır sıkıştırma."""
    if severity <= 0:
        return img
    qual = int(round(92 - 87 * severity))
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, max(2, qual)])
    return cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE) if ok else img


def occlusion(img: np.ndarray, severity: float, rng=None) -> np.ndarray:
    """Bulut / kanat / lens kirliliği: görüntünün bir kısmı kapanır."""
    if severity <= 0 or rng is None:
        return img
    out = img.copy()
    h, w = out.shape[:2]
    area = severity * 0.55 * h * w
    n_blobs = max(1, int(1 + severity * 3))
    for _ in range(n_blobs):
        r = int(np.sqrt(area / (n_blobs * np.pi)))
        cx, cy = rng.integers(0, w), rng.integers(0, h)
        cv2.circle(out, (int(cx), int(cy)), max(4, r), int(rng.integers(200, 255)), -1)
    return out


def resolution(img: np.ndarray, severity: float, rng=None) -> np.ndarray:
    """Daha ucuz / daha uzak kamera: çözünürlük kaybı."""
    if severity <= 0:
        return img
    f = 1.0 - 0.85 * severity
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(16, int(w * f)), max(16, int(h * f))),
                       interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


DEGRADATIONS = {
    "hareket bulanikligi": motion_blur,
    "sis": fog,
    "dusuk isik": low_light,
    "jpeg sikistirma": jpeg,
    "kapanma": occlusion,
    "cozunurluk kaybi": resolution,
}


def make_degrader(name: str, severity: float):
    """scripts/07_sequential.py'nin beklediği (img, rng) -> img biçiminde sarmalar."""
    fn = DEGRADATIONS[name]

    def _d(img, rng):
        return fn(img, severity, rng)

    return _d

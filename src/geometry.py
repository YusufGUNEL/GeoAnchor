"""Duruştan kaynaklanan kaymanın fotogrametrik düzeltmesi.

Sorun: eşleme bize İHA görüntüsünün MERKEZ pikselinin yere düştüğü noktayı
verir. Aradığımız ise İHA'nın kendi konumudur. Kamera dik bakmıyorsa bu ikisi
farklıdır: h irtifasında θ eğimi yerde h·tan(θ) kadar kaydırır. 466 m'de 2°
eğim 16 m eder — ölçtüğümüz hatanın tam kaynağı.

Kanal isimleri deneyle belirlendi (veri kümesi belgesi ters yazıyor):
  Kappa  -> ileri eğim (pitch),  regresyon katsayısı +0,981
  Omega  -> yana yatma (roll),   regresyon katsayısı -0,972
İkisi de ±1'e oturuyor, yani h·tan(θ) fiziği birebir doğru; sadece etiketler
yer değişmiş. Ayrıca sabit bir ileri kayma var (kamera montaj açısı / zaman
farkı) — bu kalibrasyonla bir kez ölçülür.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class AttitudeModel:
    """Duruş kaynaklı kayma modeli ve boresight kalibrasyonu.

    pitch_deg / roll_deg: kalibrasyonla bulunan sabit montaj sapmaları.
    """
    pitch_bias_deg: float = 0.0
    roll_bias_deg: float = 0.0
    pitch_sign: float = +1.0
    roll_sign: float = -1.0

    def offset_body(self, pitch_deg, roll_deg, height_m):
        """Görüntü merkezinin İHA'ya göre yerdeki kayması.

        Döndürür: (ileri_m, sağ_m) — gövde çerçevesinde.
        """
        p = np.radians(np.asarray(pitch_deg, float) + self.pitch_bias_deg)
        r = np.radians(np.asarray(roll_deg, float) + self.roll_bias_deg)
        h = np.asarray(height_m, float)
        return self.pitch_sign * h * np.tan(p), self.roll_sign * h * np.tan(r)

    def offset_ne(self, pitch_deg, roll_deg, height_m, yaw_deg):
        """Aynı kayma, kuzey/doğu bileşenleriyle."""
        fwd, rgt = self.offset_body(pitch_deg, roll_deg, height_m)
        y = np.radians(np.asarray(yaw_deg, float))
        north = fwd * np.cos(y) - rgt * np.sin(y)
        east = fwd * np.sin(y) + rgt * np.cos(y)
        return north, east

    def correct(self, lat, lon, pitch_deg, roll_deg, height_m, yaw_deg,
                m_lat: float, m_lon: float):
        """Eşlemeden gelen yer noktasını İHA konumuna çevirir (kaymayı çıkarır)."""
        n, e = self.offset_ne(pitch_deg, roll_deg, height_m, yaw_deg)
        return np.asarray(lat, float) - n / m_lat, np.asarray(lon, float) - e / m_lon


def calibrate(along_err, cross_err, pitch_deg, roll_deg, height_m) -> AttitudeModel:
    """Kalibrasyon kümesinden montaj sapmalarını bulur.

    Model tersine çevrilebilir olduğu için doğrudan çözülür, doğrusallaştırma
    gerekmez: ileri = +h·tan(pitch + bp)  =>  bp = arctan(ileri/h) - pitch.
    Aykırı eşlemelere karşı medyan alınır.
    """
    h = np.asarray(height_m, float)
    p = np.asarray(pitch_deg, float)
    r = np.asarray(roll_deg, float)
    bp = np.median(np.degrees(np.arctan(np.asarray(along_err, float) / h)) - p)
    br = np.median(np.degrees(np.arctan(-np.asarray(cross_err, float) / h)) - r)
    return AttitudeModel(pitch_bias_deg=float(bp), roll_bias_deg=float(br))


def body_from_ne(dn, de, yaw_deg):
    """Kuzey/doğu hata vektörünü gövde çerçevesine (ileri, sağ) çevirir."""
    y = np.radians(np.asarray(yaw_deg, float))
    fwd = np.asarray(dn, float) * np.cos(y) + np.asarray(de, float) * np.sin(y)
    rgt = -np.asarray(dn, float) * np.sin(y) + np.asarray(de, float) * np.cos(y)
    return fwd, rgt

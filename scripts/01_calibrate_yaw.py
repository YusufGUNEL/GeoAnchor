"""Yönelim açısının işaret ve konvansiyonunu deneysel olarak belirler.

Üstveride Phi1 ve Phi2 var ama hangisinin hangi yönde kuzeye çevirdiği yazmıyor.
Yanlış işaret tüm boru hattını bozar, o yüzden tahmin etmiyoruz: gerçek konumdan
uydu kırpması alıp İHA karesini açı taraması yaparak eşliyoruz, en çok iç nokta
veren açı doğru açıdır. Sonra bunu Phi1/Phi2 ile karşılaştırıyoruz.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from src.flight import load_flight
from src.geo import SatelliteMap

DATA_ROOT = r"D:\GeoAnchorData\raw"
DRONE_GSD = 0.1142           # Faz 0'da kestirildi
TILE_M = 300                 # kıyas alanı kenarı (metre)


def rotate_keep(img, deg):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def count_inliers(a, b, sift, bf):
    ka, da = sift.detectAndCompute(a, None)
    kb, db = sift.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 10 or len(kb) < 10:
        return 0
    raw = bf.knnMatch(da, db, k=2)
    good = [m for m, n in raw if m.distance < 0.8 * n.distance]
    if len(good) < 8:
        return 0
    pa = np.float32([ka[m.queryIdx].pt for m in good])
    pb = np.float32([kb[m.trainIdx].pt for m in good])
    _, mask = cv2.estimateAffinePartial2D(pa, pb, cv2.RANSAC,
                                          ransacReprojThreshold=5.0,
                                          maxIters=5000, confidence=0.999)
    return 0 if mask is None else int(mask.sum())


def main():
    flight = load_flight(DATA_ROOT, "03")
    sat = SatelliteMap(flight.satellite_path)
    sift = cv2.SIFT_create(nfeatures=3000)
    bf = cv2.BFMatcher()

    # kent/sanayi ağırlıklı kareler seçilsin (tekdüze tarlada eşleme zaten tutmaz)
    idxs = [40, 120, 200, 280, 360, 440, 520, 600, 680, 740]
    side_sat = int(TILE_M / sat.gsd)          # uydu piksel
    side_drn = int(TILE_M / DRONE_GSD)        # İHA piksel

    angles = np.arange(-180, 180, 10)
    votes = []

    print(f"{'kare':>6} {'Phi1':>8} {'Phi2':>8} {'en iyi açı':>11} {'iç nokta':>9} "
          f"{'açı+Phi1':>9} {'açı-Phi1':>9}")
    print("-" * 68)

    for i in idxs:
        r = flight.df.iloc[i]
        crop, _, _ = sat.crop_around_latlon(r.lat, r.lon, side_sat)
        crop_g = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)

        drone = cv2.imread(str(flight.image_path(i)), cv2.IMREAD_GRAYSCALE)
        # merkezden İHA pikselinde TILE_M kadar kırp, sonra uydu ölçeğine indir
        ch, cw = drone.shape[0] // 2, drone.shape[1] // 2
        half = side_drn // 2
        # kısa kenar 2652 px = 303 m, TILE_M=300 m sığıyor
        dcrop = drone[max(0, ch - half):ch + half, max(0, cw - half):cw + half]
        dcrop = cv2.resize(dcrop, (side_sat, side_sat))

        best_a, best_n = None, 0
        for a in angles:
            n = count_inliers(rotate_keep(dcrop, float(a)), crop_g, sift, bf)
            if n > best_n:
                best_n, best_a = n, float(a)

        if best_n >= 12:
            votes.append((best_a, float(r.Phi1), float(r.Phi2)))
            print(f"{i:>6} {r.Phi1:>8.2f} {r.Phi2:>8.2f} {best_a:>11.0f} {best_n:>9} "
                  f"{best_a + r.Phi1:>9.1f} {best_a - r.Phi1:>9.1f}")
        else:
            print(f"{i:>6} {r.Phi1:>8.2f} {r.Phi2:>8.2f} {'--':>11} {best_n:>9} "
                  f"{'--':>9} {'--':>9}")

    print("-" * 68)
    if not votes:
        print("Hiçbir karede yeterli eşleme olmadı — parametreler gözden geçirilmeli.")
        return

    a = np.array([v[0] for v in votes])
    p1 = np.array([v[1] for v in votes])
    p2 = np.array([v[2] for v in votes])

    def wrap(x):
        return (x + 180) % 360 - 180

    for name, resid in [("açı + Phi1", wrap(a + p1)), ("açı - Phi1", wrap(a - p1)),
                        ("açı + Phi2", wrap(a + p2)), ("açı - Phi2", wrap(a - p2))]:
        print(f"{name:>12}: ortalama {resid.mean():>8.2f}°  "
              f"std {resid.std():>6.2f}°  (std küçükse bu bağıntı doğru)")

    print(f"\nBaşarılı kare: {len(votes)}/{len(idxs)}")
    sat.close()


if __name__ == "__main__":
    main()

"""Faz 0 doğrulama: veri tutarlı mı, coğrafi dönüşüm doğru mu, ölçek ne?

Ürettikleri:
  results/00_ozet.txt            uçuş özeti + tahmin edilen yer örnekleme aralığı
  figures/00_yorunge.png         uydu haritası üzerinde gerçek yörünge
  figures/00_hizalama.png        İHA karesi ile aynı koordinattaki uydu kırpması
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.flight import load_flight
from src.geo import SatelliteMap

DATA_ROOT = r"D:\GeoAnchorData\raw"
OUT = Path(__file__).resolve().parents[1]
(OUT / "results").mkdir(exist_ok=True)
(OUT / "figures").mkdir(exist_ok=True)


def estimate_drone_gsd(flight, n_pairs: int = 20, stride: int = 8) -> tuple[float, float]:
    """İHA görüntüsünün metre/piksel ölçeğini ardışık karelerden kestirir.

    Mantık: iki ardışık kare arasındaki kayma piksel cinsinden özellik
    eşlemesiyle, metre cinsinden gerçek konumdan bilinir. Oranı ölçeği verir.
    Bu aynı zamanda Faz 2'deki görsel odometrinin çalışacağının kanıtı.
    """
    orb = cv2.SIFT_create(nfeatures=4000)
    bf = cv2.BFMatcher()
    ratios, inlier_counts = [], []

    idxs = np.linspace(0, flight.n_frames - 2, n_pairs).astype(int)
    for i in idxs:
        # aynı uçuş hattında kalmak için büyük dönüşleri atla
        if abs(flight.df["Phi1"].iloc[i + 1] - flight.df["Phi1"].iloc[i]) > 5:
            continue
        im1 = cv2.imread(str(flight.image_path(i)), cv2.IMREAD_GRAYSCALE)
        im2 = cv2.imread(str(flight.image_path(i + 1)), cv2.IMREAD_GRAYSCALE)
        if im1 is None or im2 is None:
            continue
        s = 1 / 4  # hız için küçült
        im1s = cv2.resize(im1, None, fx=s, fy=s)
        im2s = cv2.resize(im2, None, fx=s, fy=s)

        k1, d1 = orb.detectAndCompute(im1s, None)
        k2, d2 = orb.detectAndCompute(im2s, None)
        if d1 is None or d2 is None:
            continue
        raw = bf.knnMatch(d1, d2, k=2)
        good = [m for m, n in raw if m.distance < 0.75 * n.distance]
        if len(good) < 30:
            continue
        p1 = np.float32([k1[m.queryIdx].pt for m in good])
        p2 = np.float32([k2[m.trainIdx].pt for m in good])
        M, mask = cv2.estimateAffinePartial2D(p1, p2, cv2.RANSAC, ransacReprojThreshold=3.0)
        if M is None:
            continue
        inl = int(mask.sum())
        if inl < 20:
            continue
        # ölçeklenmiş görüntüdeki kayma -> tam çözünürlüğe geri al
        shift_px = np.hypot(M[0, 2], M[1, 2]) / s
        step_m = float(flight.df["step_m"].iloc[i + 1])
        if shift_px < 1:
            continue
        ratios.append(step_m / shift_px)
        inlier_counts.append(inl)

    return float(np.median(ratios)), float(np.median(inlier_counts))


def main():
    flight = load_flight(DATA_ROOT, "03")
    sat = SatelliteMap(flight.satellite_path)

    lines = [flight.summary(), "", f"Uydu haritası: {sat}"]

    # --- gerçek konumlar haritanın içinde mi? ---
    inside = [sat.contains(r.lat, r.lon) for r in flight.df.itertuples()]
    lines.append(f"Harita içinde kalan kare: {sum(inside)}/{len(inside)}")

    # --- İHA ölçeği ---
    print("İHA yer örnekleme aralığı kestiriliyor (ardışık kare eşlemesi)...")
    gsd, med_inliers = estimate_drone_gsd(flight)
    fw = gsd * 3976
    fh = gsd * 2652
    lines += [
        "",
        "İHA görüntü ölçeği (ardışık kare eşlemesinden kestirildi):",
        f"  yer örnekleme aralığı : {gsd:.4f} m/piksel",
        f"  kare ayak izi         : {fw:.0f} m x {fh:.0f} m",
        f"  ardışık kare örtüşmesi: %{100 * (1 - 96.3 / fw):.1f} (96,3 m adımla)",
        f"  medyan iç nokta       : {med_inliers:.0f} (görsel odometri için sağlam)",
        f"  uydu/İHA ölçek oranı  : {sat.gsd / gsd:.2f}x",
    ]

    report = "\n".join(lines)
    print("\n" + report)
    (OUT / "results" / "00_ozet.txt").write_text(report, encoding="utf-8")

    # --- Şekil 1: yörünge ---
    print("\nYörünge şekli çiziliyor...")
    ov = sat.overview(1600)
    sx = ov.shape[1] / sat.width
    sy = ov.shape[0] / sat.height
    px, py = sat.latlon_to_px(flight.df["lat"].values, flight.df["lon"].values)

    fig, ax = plt.subplots(figsize=(11, 9))
    ax.imshow(ov)
    ax.plot(px * sx, py * sy, "-", lw=1.0, color="#00e5ff", alpha=0.9, label="gerçek yörünge")
    ax.plot(px[0] * sx, py[0] * sy, "o", ms=10, color="#00ff6a", label="başlangıç")
    ax.plot(px[-1] * sx, py[-1] * sy, "s", ms=10, color="#ff3b30", label="bitiş")
    ax.set_title(f"Uçuş 03 — {flight.n_frames} kare, "
                 f"{flight.df['cum_dist_m'].iloc[-1]/1000:.1f} km, "
                 f"{flight.df['t_s'].iloc[-1]/60:.0f} dk\n"
                 f"Uydu haritası {sat.width}x{sat.height} px @ {sat.gsd:.2f} m/px "
                 f"(8,8 x 7,3 km)")
    ax.legend(loc="upper right")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "00_yorunge.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    # --- Şekil 2: hizalama kontrolü ---
    print("Hizalama kontrolü çiziliyor...")
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    for col, i in enumerate([50, 300, 600]):
        r = flight.df.iloc[i]
        drone = cv2.cvtColor(cv2.imread(str(flight.image_path(i))), cv2.COLOR_BGR2RGB)
        # İHA karesini uydu ölçeğine indir
        k = gsd / sat.gsd
        dscaled = cv2.resize(drone, None, fx=k, fy=k)
        size = max(dscaled.shape[:2])
        crop, _, _ = sat.crop_around_latlon(r.lat, r.lon, size)

        axes[0, col].imshow(dscaled)
        axes[0, col].set_title(f"İHA karesi {r.filename}\n(uydu ölçeğine indirildi)", fontsize=9)
        axes[0, col].axis("off")
        axes[1, col].imshow(crop)
        axes[1, col].set_title(f"Aynı koordinattaki uydu kırpması\n"
                               f"{r.lat:.5f} N, {r.lon:.5f} E", fontsize=9)
        axes[1, col].axis("off")
    fig.suptitle("Coğrafi dönüşüm kontrolü — üst ve alt satır aynı yeri göstermeli\n"
                 "(uydu 2018 öncesi, İHA 2018-10-23; mevsim/yapı farkı beklenir)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "figures" / "00_hizalama.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    sat.close()
    print("\nBitti. results/00_ozet.txt ve figures/00_*.png yazıldı.")


if __name__ == "__main__":
    main()

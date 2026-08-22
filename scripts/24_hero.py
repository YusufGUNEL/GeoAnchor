"""Depo kapak gorseli — ilk bakista projeyi anlatan tek resim.

Uc panel: IHA ne goruyor / haritada nerede oldugunu nasil biliyor / hata nasil
seyrediyor. Ustte tek satirlik sonuc.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from src.flight import load_flight
from src.geo import SatelliteMap, local_m_to_latlon

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(r"D:\GeoAnchorData\cache")
BG = "#0b0d12"
C_GT = "#8fd6ff"
C_PF = "#22e07a"
C_VO = "#ff4d6d"
FRAME = 430


def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    z = np.load(ROOT / "results" / "07_sequential_ana.npz")
    vo = np.load(ROOT / "results" / "06_odometry.npz")
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])

    ov_full = sat.overview(1300)
    sx, sy = ov_full.shape[1] / sat.width, ov_full.shape[0] / sat.height

    def to_px(n, e):
        la, lo = local_m_to_latlon(n, e, lat0, lon0)
        x, y = sat.latlon_to_px(la, lo)
        return np.asarray(x) * sx, np.asarray(y) * sy

    gx, gy = to_px(d["north_m"].values, d["east_m"].values)
    # yorungenin sigdigi bolgeye kirp: panel bos kalmasin
    m = 60
    x0 = max(0, int(gx.min() - m)); x1 = min(ov_full.shape[1], int(gx.max() + m))
    y0 = max(0, int(gy.min() - m)); y1 = min(ov_full.shape[0], int(gy.max() + m))
    ov = ov_full[y0:y1, x0:x1]
    gx, gy = gx - x0, gy - y0
    px, py = to_px(z["north"], z["east"])
    px, py = px - x0, py - y0
    vx, vy = to_px(vo["vo_north"], vo["vo_east"])
    vx, vy = vx - x0, vy - y0
    km = d["cum_dist_m"].values / 1000
    err = z["err"]

    fig = plt.figure(figsize=(17, 6.4), dpi=110)
    fig.patch.set_facecolor(BG)

    fig.text(0.5, 0.962, "GeoAnchor  —  GNSS-denied absolute visual localization for UAVs",
             ha="center", color="w", fontsize=20, weight="bold")
    fig.text(0.5, 0.902,
             "9 real survey flights  ·  406–2572 m altitude  ·  median 8–25 m where the map is usable  "
             "·  odometry alone drifts 2.8 km in 74 km  ·  runs in 1.4 GB VRAM",
             ha="center", color="#9aa3b2", fontsize=11.5)

    # --- panel 1: kamera ---
    ax = fig.add_axes([0.012, 0.06, 0.245, 0.78])
    ax.imshow(np.ascontiguousarray(q[FRAME]))
    ax.plot(320, 320, "+", color=C_PF, ms=22, mew=2.5)
    ax.set_title("what the drone sees", color="w", fontsize=13, pad=6)
    ax.axis("off")

    # --- panel 2: harita ---
    ax = fig.add_axes([0.272, 0.055, 0.41, 0.755])
    ax.imshow(ov)
    ax.plot(gx, gy, "-", lw=5.0, color="#ffffff", alpha=0.95)
    ax.plot(vx, vy, "-", lw=1.5, color=C_VO, alpha=0.9)
    ax.plot(px, py, "-", lw=1.5, color=C_PF)
    ax.plot(px[FRAME], py[FRAME], "o", ms=11, color=C_PF, mec="k", mew=0.8, zorder=6)
    ax.set_title("GREEN = this system   ·   RED = what happens without it",
                 color="w", fontsize=13, pad=6)
    ax.axis("off")
    ax.add_patch(Rectangle((0.012, 0.012), 0.62, 0.185, transform=ax.transAxes,
                           color="#000000", alpha=0.62, zorder=7))
    for i, (c, t) in enumerate([("#ffffff", "truth  (where the drone really was)"),
                                (C_PF, "GeoAnchor  — tracks the truth"),
                                (C_VO, "without GeoAnchor — drifts off the map")]):
        ax.add_patch(Rectangle((0.032, 0.148 - i * 0.058), 0.038, 0.026,
                               transform=ax.transAxes, color=c, zorder=8))
        ax.text(0.082, 0.161 - i * 0.058, t, transform=ax.transAxes,
                color="w", fontsize=10.5, va="center", zorder=8)

    # --- panel 3: hata ---
    ax = fig.add_axes([0.725, 0.155, 0.258, 0.63])
    ax.set_facecolor("#141822")
    ax.plot(km, vo["err"], color=C_VO, lw=1.8, label="without GeoAnchor")
    ax.plot(km, err, color=C_PF, lw=1.8, label="with GeoAnchor")
    ax.set_yscale("log")
    ax.set_ylim(1, 5000)
    ax.set_xlim(0, km[-1])
    ax.set_xlabel("distance flown (km)", color="w", fontsize=11)
    ax.set_ylabel("position error (m)", color="w", fontsize=11)
    ax.tick_params(colors="w", labelsize=9)
    for s in ax.spines.values():
        s.set_color("#39404f")
    ax.grid(alpha=0.16, which="both", color="#7a8496")
    ax.legend(fontsize=10, facecolor="#141822", edgecolor="#39404f",
              labelcolor="w", loc="center left")
    ax.annotate("", xy=(km[-1] * 0.62, 2600), xytext=(km[-1] * 0.62, 7),
                arrowprops=dict(arrowstyle="<->", color="#ffd166", lw=1.8))
    ax.text(km[-1] * 0.60, 130, "370x\nbetter", color="#ffd166", fontsize=12,
            weight="bold", ha="right", va="center")
    ax.set_title("bigger gap = bigger win", color="w", fontsize=13, pad=6)

    fig.savefig(ROOT / "figures" / "00_hero.png", dpi=110,
                facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    sat.close()
    p = ROOT / "figures" / "00_hero.png"
    print("figures/00_hero.png yazildi (%.1f MB)" % (p.stat().st_size / 1e6))


if __name__ == "__main__":
    main()

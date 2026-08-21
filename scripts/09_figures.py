"""Faz 5/6 — sonuc sekilleri.

Uretilenler (figures/):
  10_karsilastirma.png   iki panel: odometrinin surukleniHi vs harita capali sistem
  11_hata_egrisi.png     mesafeye gore hata
  12_kapsama.png         hangi karede konum uretilebildi + eslem maliyeti
  13_dagilim.png         hata birikimli dagilimi (uc yontem bir arada)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.flight import load_flight
from src.geo import SatelliteMap, latlon_to_local_m, local_m_to_latlon

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
RES = ROOT / "results"
FIG.mkdir(exist_ok=True)

C_GT = "#00e5ff"
C_SF = "#ffb000"
C_VO = "#ff2d55"
C_PF = "#00ff6a"

T_SOL = "Sadece gorsel odometri ne yapiyor?\nSuruklenme IHA'yi haritanin disina tasiyor"
T_SAG = "Harita capasi takilinca\nYorunge gercegin ustunde kaliyor"
T_CDF = "Hata birikimli dagilimi\nSola ve yukariya yaslanan egri iyidir"
T_ERR = "Hata mesafeyle nasil degisiyor?\nOdometri surukleniyor, fuzyon sabit kaliyor"


def load_all():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    d = flight.df
    data = {"flight": flight, "gt_n": d["north_m"].values,
            "gt_e": d["east_m"].values, "dist": d["cum_dist_m"].values}
    p = RES / "05_single_frame.npz"
    if p.exists():
        z = np.load(p)
        lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
        n, e = latlon_to_local_m(z["lat"], z["lon"], lat0, lon0)
        data["sf"] = {"north": n, "east": e, "err": z["err"],
                      "n_tried": z["n_tried"], "ms": z["ms"]}
    p = RES / "06_odometry.npz"
    if p.exists():
        z = np.load(p)
        data["vo"] = {"north": z["vo_north"], "east": z["vo_east"], "err": z["err"]}
    p = RES / "07_sequential_ana.npz"
    if p.exists():
        z = np.load(p)
        data["pf"] = {"north": z["north"], "east": z["east"], "err": z["err"],
                      "spread": z["spread"], "n_loftr": z["n_loftr"], "ms": z["ms"]}
    return data


def make_to_px(sat, ov, lat0, lon0):
    sx, sy = ov.shape[1] / sat.width, ov.shape[0] / sat.height

    def to_px(n, e):
        la, lo = local_m_to_latlon(n, e, lat0, lon0)
        x, y = sat.latlon_to_px(la, lo)
        return np.asarray(x) * sx, np.asarray(y) * sy
    return to_px


def fig_trajectories(D):
    flight = D["flight"]
    sat = SatelliteMap(flight.satellite_path)
    ov = sat.overview(1500)
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    to_px = make_to_px(sat, ov, lat0, lon0)
    gx, gy = to_px(D["gt_n"], D["gt_e"])

    fig, axes = plt.subplots(1, 2, figsize=(19, 9))

    ax = axes[0]
    ax.imshow(ov, alpha=0.5)
    ax.plot(gx, gy, "-", lw=2.4, color=C_GT, label="gercek yorunge", zorder=5)
    if "vo" in D:
        vx, vy = to_px(D["vo"]["north"], D["vo"]["east"])
        lbl = "sadece gorsel odometri, 74 km sonra {:.0f} m sapma".format(
            D["vo"]["err"][-1])
        ax.plot(vx, vy, "-", lw=1.8, color=C_VO, alpha=0.95, zorder=4, label=lbl)
        ax.plot(vx[-1], vy[-1], "X", ms=14, color=C_VO, mec="k", mew=0.8, zorder=6)
    ax.set_title(T_SOL, fontsize=13)
    ax.legend(loc="lower left", fontsize=10, framealpha=0.9)
    ax.set_aspect("equal")
    ax.axis("off")

    ax = axes[1]
    ax.imshow(ov)
    ax.plot(gx, gy, "-", lw=5.0, color="#ffffff", alpha=0.9,
            label="gercek yorunge (kalin beyaz)", zorder=4)
    if "sf" in D:
        m = np.isfinite(D["sf"]["north"])
        sxp, syp = to_px(D["sf"]["north"][m], D["sf"]["east"][m])
        ax.plot(sxp, syp, ".", ms=4.5, color=C_SF, alpha=0.95, zorder=5,
                label="tek kare - sadece %{:.0f} karede sonuc".format(m.mean() * 100))
    if "pf" in D:
        px, py = to_px(D["pf"]["north"], D["pf"]["east"])
        e = D["pf"]["err"]
        ax.plot(px, py, "-", lw=1.5, color=C_PF, alpha=0.95, zorder=6,
                label="sirali fuzyon - %100 kare, medyan {:.1f} m".format(
                    np.nanmedian(e)))
        bad = e > 50
        if bad.any():
            ax.plot(px[bad], py[bad], ".", ms=6, color="#ff2d55", zorder=7,
                    label="eslemenin coktugu kesimler (%{:.1f})".format(
                        bad.mean() * 100))
    ax.set_title(T_SAG, fontsize=13)
    ax.legend(loc="upper right", fontsize=10, framealpha=0.9)
    ax.axis("off")

    fig.suptitle("GPS'siz mutlak konumlandirma - Taizhou, 74 km, 768 kare, "
                 "8,8 x 7,3 km uydu haritasi", fontsize=15, y=0.99)
    fig.tight_layout()
    fig.savefig(FIG / "10_karsilastirma.png", dpi=125, bbox_inches="tight")
    plt.close(fig)
    sat.close()
    print("  10_karsilastirma.png")


def fig_cdf(D):
    n_tot = len(D["gt_n"])
    fig, ax = plt.subplots(figsize=(10, 6.5))
    for key, color, name in [("sf", C_SF, "tek kare (harita geneli arama)"),
                             ("pf", C_PF, "sirali fuzyon")]:
        if key not in D:
            continue
        e = D[key]["err"]
        e = np.sort(e[np.isfinite(e)])
        ys = np.arange(1, len(e) + 1) / n_tot * 100
        ax.plot(e, ys, lw=2.4, color=color, label="{} (n={})".format(name, len(e)))
    if "vo" in D:
        e = np.sort(D["vo"]["err"])
        ax.plot(e, np.arange(1, len(e) + 1) / n_tot * 100, lw=2.0,
                color=C_VO, label="sadece gorsel odometri")
    for t in (5, 10, 20):
        ax.axvline(t, color="#888", ls=":", lw=1)
        ax.text(t, 3, "{} m".format(t), color="#666", fontsize=9, ha="center")
    ax.set_xscale("log")
    ax.set_xlim(0.5, 5000)
    ax.set_ylim(0, 100)
    ax.set_xlabel("konum hatasi (m, logaritmik)")
    ax.set_ylabel("bu hatanin altinda kalan kare orani (%)")
    ax.set_title(T_CDF, fontsize=13)
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=10, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "13_dagilim.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("  13_dagilim.png")


def fig_error_curve(D):
    km = D["dist"] / 1000
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    ax = axes[0]
    if "vo" in D:
        ax.plot(km, D["vo"]["err"], color=C_VO, lw=1.6,
                label="sadece gorsel odometri")
    if "sf" in D:
        m = np.isfinite(D["sf"]["err"])
        ax.plot(km[m], D["sf"]["err"][m], ".", ms=3, color=C_SF, alpha=0.6,
                label="tek kare (cozulen kareler)")
    if "pf" in D:
        ax.plot(km, D["pf"]["err"], color=C_PF, lw=1.6, label="sirali fuzyon")
    ax.set_yscale("log")
    ax.set_ylabel("konum hatasi (m, logaritmik)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=10)
    ax.set_title(T_ERR, fontsize=13)

    ax = axes[1]
    if "pf" in D:
        ax.plot(km, D["pf"]["err"], color=C_PF, lw=1.4, label="sirali fuzyon")
        ax.fill_between(km, 0, D["pf"]["spread"], color=C_PF, alpha=0.2,
                        label="suzgecin kendi belirsizlik kestirimi")
    ax.set_xlabel("kat edilen yol (km)")
    ax.set_ylabel("hata (m)")
    ax.set_ylim(0, 60)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "11_hata_egrisi.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("  11_hata_egrisi.png")


def fig_coverage(D):
    km = D["dist"] / 1000
    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1, 2]})
    ax = axes[0]
    if "sf" in D:
        ok = np.isfinite(D["sf"]["err"])
        ax.fill_between(km, 0, ok.astype(float), step="mid", color=C_SF, alpha=0.85)
        ax.set_ylabel("tek kare", fontsize=9)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["yok", "var"], fontsize=8)
        ax.set_title("Hangi karede konum uretilebildi?  tek kare: %{:.1f}".format(
            ok.mean() * 100), fontsize=12)
    ax = axes[1]
    if "pf" in D:
        ok2 = np.isfinite(D["pf"]["err"])
        ax.fill_between(km, 0, ok2.astype(float), step="mid", color=C_PF, alpha=0.85)
        ax.set_ylabel("fuzyon\n%{:.0f}".format(ok2.mean() * 100), fontsize=9)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["yok", "var"], fontsize=8)
    ax = axes[2]
    if "sf" in D:
        ax.plot(km, D["sf"]["n_tried"], lw=0.9, color=C_SF, alpha=0.85,
                label="tek kare (ort {:.2f})".format(np.nanmean(D["sf"]["n_tried"])))
    if "pf" in D:
        ax.plot(km, D["pf"]["n_loftr"], lw=0.9, color=C_PF,
                label="sirali fuzyon (ort {:.2f})".format(
                    np.nanmean(D["pf"]["n_loftr"])))
    ax.set_ylabel("kare basina\nesleme cagrisi", fontsize=9)
    ax.set_xlabel("kat edilen yol (km)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG / "12_kapsama.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("  12_kapsama.png")


def main():
    D = load_all()
    print("Sekiller uretiliyor:")
    fig_trajectories(D)
    fig_cdf(D)
    fig_error_curve(D)
    fig_coverage(D)
    print("Bitti.")


if __name__ == "__main__":
    main()

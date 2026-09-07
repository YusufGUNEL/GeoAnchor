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

from src.figtext import figdir, num, pct, pick
from src.flight import load_flight
from src.geo import SatelliteMap, latlon_to_local_m, local_m_to_latlon

ROOT = Path(__file__).resolve().parents[1]
FIG = figdir()
RES = ROOT / "results"

C_GT = "#00e5ff"
C_SF = "#ffb000"
C_VO = "#ff2d55"
C_PF = "#00ff6a"

T = pick({
 "en": {
  "left": "WITHOUT THIS SYSTEM\nodometry alone drifts the UAV clean off the map",
  "right": "WITH THIS SYSTEM\nthe whole route stays on the truth; colour is the error",
  "suptitle": ("Absolute positioning with no GNSS — Taizhou, 74 km, 768 frames, "
               "8.8 x 7.3 km satellite map"),
  "gt": "true route (where the drone really was)",
  "vo": "where it thinks it is without the system: {:.0f} m off after 74 km",
  "err_cb": "position error (m)",
  "collapse": "matching collapsed here ({} frames)",
  "sf_pts": "single-frame method — a result on only {} of frames",
  "cdf_sf": "single frame (search the whole map) (n={})",
  "cdf_pf": "THIS SYSTEM (sequential fusion) (n={})",
  "cdf_vo": "WITHOUT the system (odometry only)",
  "cdf_x": "position error (m, log scale)",
  "cdf_y": "frames below this error (%)",
  "cdf_title": "Error distribution\nfurther LEFT and UP is better",
  "err_title": ("How does the error grow with distance?\n"
                "the bigger the gap between RED and GREEN, the better"),
  "err_vo": "WITHOUT the system (odometry only)",
  "err_sf": "single frame (frames it solved)",
  "err_pf": "THIS SYSTEM",
  "err_spread": "the filter's own uncertainty estimate",
  "err_y": "position error (m, log scale)",
  "err_y2": "error (m)",
  "err_x": "distance flown (km)",
  "cov_title": "Which frames produced a position?  single frame: {}",
  "cov_sf": "single frame",
  "cov_pf": "fusion\n{}",
  "cov_no": "none",
  "cov_yes": "yes",
  "cov_calls": "matching calls\nper frame",
  "cov_l_sf": "single frame (mean {})",
  "cov_l_pf": "sequential fusion (mean {})",
 },
 "tr": {
  "left": "BU SISTEM OLMASAYDI\nSadece odometri: suruklenme IHA'yi haritanin DISINA tasiyor",
  "right": "BU SISTEMLE\nButun rota gercegin uzerinde kaliyor; renk hatayi gosteriyor",
  "suptitle": ("GPS'siz mutlak konumlandirma — Taizhou, 74 km, 768 kare, "
               "8,8 x 7,3 km uydu haritasi"),
  "gt": "GERCEK yorunge (drone gercekte buradaydi)",
  "vo": "sistem OLMADAN nerede sandigi: 74 km sonra {:.0f} m sapma",
  "err_cb": "konum hatasi (m)",
  "collapse": "eslemenin coktugu yerler ({} kare)",
  "sf_pts": "tek kare yontemi — sadece {} karede sonuc",
  "cdf_sf": "tek kare (harita geneli arama) (n={})",
  "cdf_pf": "BU SISTEM (sirali fuzyon) (n={})",
  "cdf_vo": "sistem OLMADAN (sadece odometri)",
  "cdf_x": "konum hatasi (m, logaritmik)",
  "cdf_y": "bu hatanin altinda kalan kare orani (%)",
  "cdf_title": "Hata birikimli dagilimi\nSOLA ve YUKARIYA yaslanan egri IYIDIR",
  "err_title": ("Hata mesafeyle nasil degisiyor?\n"
                "KIRMIZI ile YESIL arasindaki fark ne kadar buyukse o kadar iyi"),
  "err_vo": "sistem OLMADAN (sadece odometri)",
  "err_sf": "tek kare (cozulen kareler)",
  "err_pf": "BU SISTEM",
  "err_spread": "suzgecin kendi belirsizlik kestirimi",
  "err_y": "konum hatasi (m, logaritmik)",
  "err_y2": "hata (m)",
  "err_x": "kat edilen yol (km)",
  "cov_title": "Hangi karede konum uretilebildi?  tek kare: {}",
  "cov_sf": "tek kare",
  "cov_pf": "fuzyon\n{}",
  "cov_no": "yok",
  "cov_yes": "var",
  "cov_calls": "kare basina\nesleme cagrisi",
  "cov_l_sf": "tek kare (ort {})",
  "cov_l_pf": "sirali fuzyon (ort {})",
 },
})


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
    """Two panels, one frame of reference, and no overlapping tracks.

    The old version drew truth and estimate as two thick lines on top of each
    other across seventeen parallel survey legs. At 8.8 km wide a 6 m error is
    smaller than the line itself, so the two could never be told apart -- the
    panel read as a hatch pattern and its white legend swatch was invisible on
    a white box. Overlaying them can only ever show gross divergence, which is
    what the left panel is for.

    So the right panel draws one track, coloured by error. That removes the
    tangle and says more: not just that the estimate is good, but where on the
    route it is worst.
    """
    flight = D["flight"]
    sat = SatelliteMap(flight.satellite_path)
    ov = sat.overview(1500)
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    to_px = make_to_px(sat, ov, lat0, lon0)
    gx, gy = to_px(D["gt_n"], D["gt_e"])

    fig, axes = plt.subplots(1, 2, figsize=(18, 8.4))

    # --- left: what happens without the system ---
    ax = axes[0]
    ax.imshow(ov, alpha=0.55)
    ax.plot(gx, gy, "-", lw=4.0, color="w", alpha=0.9, zorder=4)
    ax.plot(gx, gy, "-", lw=1.6, color=C_GT, zorder=5, label=T["gt"])
    if "vo" in D:
        vx, vy = to_px(D["vo"]["north"], D["vo"]["east"])
        ax.plot(vx, vy, "-", lw=1.8, color=C_VO, zorder=6,
                label=T["vo"].format(D["vo"]["err"][-1]))
        ax.plot(vx[-1], vy[-1], "X", ms=15, color=C_VO, mec="k", mew=1.0, zorder=7)
    ax.set_title(T["left"], fontsize=13)

    # --- right: the same route, coloured by how wrong it is ---
    ax = axes[1]
    ax.imshow(ov, alpha=0.55)
    sc = None
    if "pf" in D:
        px, py = to_px(D["pf"]["north"], D["pf"]["east"])
        e = D["pf"]["err"]
        # Clipped at 20 m so the colour spends its range on the errors that
        # actually occur; the collapses are marked separately below.
        sc = ax.scatter(px, py, c=np.clip(e, 0, 20), s=6, cmap="viridis",
                        vmin=0, vmax=20, zorder=5)
        bad = e > 50
        if bad.any():
            ax.plot(px[bad], py[bad], "o", ms=7, mfc="none", mec=C_VO, mew=1.4,
                    zorder=6, label=T["collapse"].format(int(bad.sum())))
    ax.set_title(T["right"], fontsize=13)

    # Both panels share the union of the extents: the drift has to be read
    # against the same frame the estimate is drawn in, not a rescaled one.
    xs = [gx, [0, ov.shape[1]]]
    ys = [gy, [0, ov.shape[0]]]
    if "vo" in D:
        xs.append(vx); ys.append(vy)
    xs, ys = np.concatenate(xs), np.concatenate(ys)
    pad = 0.03 * max(np.ptp(xs), np.ptp(ys))
    for a in axes:
        a.set_xlim(xs.min() - pad, xs.max() + pad)
        a.set_ylim(ys.max() + pad, ys.min() - pad)
        a.set_aspect("equal")
        a.axis("off")
        leg = a.legend(loc="lower left", fontsize=11, framealpha=0.9,
                       facecolor="#1a1d24", edgecolor="none")
        for txt in leg.get_texts():
            txt.set_color("w")

    if sc is not None:
        cb = fig.colorbar(sc, ax=axes[1], fraction=0.036, pad=0.02)
        cb.set_label(T["err_cb"], fontsize=11)

    fig.suptitle(T["suptitle"], fontsize=15, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "10_karsilastirma.png", dpi=125, bbox_inches="tight")
    plt.close(fig)
    sat.close()
    print("  10_karsilastirma.png")


def fig_cdf(D):
    n_tot = len(D["gt_n"])
    fig, ax = plt.subplots(figsize=(10, 6.5))
    for key, color, tmpl in [("sf", C_SF, T["cdf_sf"]), ("pf", C_PF, T["cdf_pf"])]:
        if key not in D:
            continue
        e = D[key]["err"]
        e = np.sort(e[np.isfinite(e)])
        ys = np.arange(1, len(e) + 1) / n_tot * 100
        ax.plot(e, ys, lw=2.4, color=color, label=tmpl.format(len(e)))
    if "vo" in D:
        e = np.sort(D["vo"]["err"])
        ax.plot(e, np.arange(1, len(e) + 1) / n_tot * 100, lw=2.0,
                color=C_VO, label=T["cdf_vo"])
    for t in (5, 10, 20):
        ax.axvline(t, color="#888", ls=":", lw=1)
        ax.text(t, 3, "{} m".format(t), color="#666", fontsize=9, ha="center")
    ax.set_xscale("log")
    ax.set_xlim(0.5, 5000)
    ax.set_ylim(0, 100)
    ax.set_xlabel(T["cdf_x"])
    ax.set_ylabel(T["cdf_y"])
    ax.set_title(T["cdf_title"], fontsize=13)
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
        ax.plot(km, D["vo"]["err"], color=C_VO, lw=1.6, label=T["err_vo"])
    if "sf" in D:
        m = np.isfinite(D["sf"]["err"])
        ax.plot(km[m], D["sf"]["err"][m], ".", ms=3, color=C_SF, alpha=0.6,
                label=T["err_sf"])
    if "pf" in D:
        ax.plot(km, D["pf"]["err"], color=C_PF, lw=1.6, label=T["err_pf"])
    ax.set_yscale("log")
    ax.set_ylabel(T["err_y"])
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=10)
    ax.set_title(T["err_title"], fontsize=13)

    ax = axes[1]
    if "pf" in D:
        ax.plot(km, D["pf"]["err"], color=C_PF, lw=1.4, label=T["err_pf"])
        ax.fill_between(km, 0, D["pf"]["spread"], color=C_PF, alpha=0.2,
                        label=T["err_spread"])
    ax.set_xlabel(T["err_x"])
    ax.set_ylabel(T["err_y2"])
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
        ax.set_ylabel(T["cov_sf"], fontsize=9)
        ax.set_yticks([0, 1])
        ax.set_yticklabels([T["cov_no"], T["cov_yes"]], fontsize=8)
        ax.set_title(T["cov_title"].format(pct(ok.mean() * 100, 1)), fontsize=12)
    ax = axes[1]
    if "pf" in D:
        ok2 = np.isfinite(D["pf"]["err"])
        ax.fill_between(km, 0, ok2.astype(float), step="mid", color=C_PF, alpha=0.85)
        ax.set_ylabel(T["cov_pf"].format(pct(ok2.mean() * 100)), fontsize=9)
        ax.set_yticks([0, 1])
        ax.set_yticklabels([T["cov_no"], T["cov_yes"]], fontsize=8)
    ax = axes[2]
    if "sf" in D:
        ax.plot(km, D["sf"]["n_tried"], lw=0.9, color=C_SF, alpha=0.85,
                label=T["cov_l_sf"].format(num(np.nanmean(D["sf"]["n_tried"]), 2)))
    if "pf" in D:
        ax.plot(km, D["pf"]["n_loftr"], lw=0.9, color=C_PF,
                label=T["cov_l_pf"].format(num(np.nanmean(D["pf"]["n_loftr"]), 2)))
    ax.set_ylabel(T["cov_calls"], fontsize=9)
    ax.set_xlabel(T["err_x"])
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

"""Paper figures, in English and at IEEE column width.

The figures under figures/ are labelled in Turkish and sized for a README, so
they cannot go into the manuscript as they are. This script rebuilds the three
that carry the paper's arguments, reading the same result files the text quotes
so the figures cannot drift away from the numbers:

  fig1_trajectory.pdf   flight 03 over its orthophoto: ground truth, odometry
                        alone walking off the map, and the fused estimate.
                        Two columns wide -- this one has to be seen.
  fig2_cdf.pdf          error CDF for the three methods. One column.
  fig3_law.pdf          match rate against final error across ten flights,
                        with the threshold. One column.

Vector output throughout; the orthophoto panel carries an embedded raster,
which is what makes it the only figure that needs the dataset on disk. If the
dataset is missing that figure is skipped and the other two still build.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = ROOT / "paper" / "figures"
DATA_ROOT = Path(r"D:\GeoAnchorData\raw")

# IEEEtran: a column is 3.5 in, the text block 7.16 in. Type sizes are set
# below the body size so the figure text lands near the caption's 8 pt.
COL, FULL = 3.5, 7.16
C_GT, C_SF, C_VO, C_PF = "#0aa5c4", "#e8a33d", "#d1345b", "#1b9e5a"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 7.5,
    "axes.labelsize": 7.5,
    "axes.titlesize": 8,
    "legend.fontsize": 6.8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.2,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
})

# Matplotlib stamps a creation date into every PDF, so rebuilding identical
# figures still shows up as a change in git. Dropping it makes the output a
# function of the data alone: if the file differs, a number differed.
PDF_META = {"CreationDate": None}


def fig1_trajectory() -> bool:
    """Ground truth, odometry and fusion over the flight 03 orthophoto."""
    tif = DATA_ROOT / "03" / "satellite03.tif"
    if not tif.exists():
        print(f"  atlandi: {tif} yok (veri seti diskte degil)")
        return False

    from src.flight import load_flight
    from src.geo import SatelliteMap, local_m_to_latlon

    flight = load_flight(DATA_ROOT, "03")
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    sat = SatelliteMap(flight.satellite_path)
    ov = sat.overview(1600)
    sx, sy = ov.shape[1] / sat.width, ov.shape[0] / sat.height

    def to_px(n, e):
        la, lo = local_m_to_latlon(n, e, lat0, lon0)
        x, y = sat.latlon_to_px(la, lo)
        return np.asarray(x) * sx, np.asarray(y) * sy

    gx, gy = to_px(d["north_m"].values, d["east_m"].values)
    vo = np.load(RES / "06_odometry.npz")
    pf = np.load(RES / "07_sequential_ana.npz")
    vx, vy = to_px(vo["vo_north"], vo["vo_east"])
    px, py = to_px(pf["north"], pf["east"])
    err = pf["err"]

    fig, axes = plt.subplots(1, 2, figsize=(FULL, FULL * 0.44))

    ax = axes[0]
    ax.imshow(ov, alpha=0.55)
    ax.plot(gx, gy, "-", lw=2.2, color="w", zorder=3)
    ax.plot(gx, gy, "-", lw=1.1, color=C_GT, zorder=4, label="ground truth")
    ax.plot(vx, vy, "-", lw=1.0, color=C_VO, zorder=5,
            label=f"odometry only ({vo['err'][-1]:.0f} m final)")
    ax.plot(vx[-1], vy[-1], "X", ms=5, color=C_VO, mec="k", mew=0.4, zorder=6)
    ax.set_title("(a) without map anchoring", fontsize=8)

    ax = axes[1]
    ax.imshow(ov, alpha=0.55)
    ax.plot(gx, gy, "-", lw=2.2, color="w", zorder=3)
    ax.plot(gx, gy, "-", lw=1.1, color=C_GT, zorder=4, label="ground truth")
    ax.plot(px, py, "-", lw=0.8, color=C_PF, zorder=5,
            label=f"proposed ({np.nanmedian(err):.1f} m median, 100% coverage)")
    bad = err > 50
    if bad.any():
        ax.plot(px[bad], py[bad], ".", ms=2.2, color=C_VO, zorder=6,
                label=f"matching collapsed ({100 * bad.mean():.1f}% of frames)")
    ax.set_title("(b) proposed system", fontsize=8)

    # Both panels get the union of the two extents. The odometry track leaves
    # the basemap, and if each panel scaled to its own contents the reader
    # would be comparing two different maps -- the drift has to be read
    # against the same frame the fused estimate is drawn in.
    xs = np.concatenate([gx, vx, px, [0, ov.shape[1]]])
    ys = np.concatenate([gy, vy, py, [0, ov.shape[0]]])
    pad = 0.03 * max(np.ptp(xs), np.ptp(ys))
    for ax, loc in zip(axes, ("upper right", "lower right")):
        ax.set_xlim(xs.min() - pad, xs.max() + pad)
        ax.set_ylim(ys.max() + pad, ys.min() - pad)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.legend(loc=loc, fontsize=6, framealpha=0.88,
                  borderpad=0.3, handlelength=1.4)

    # A scale bar says more about the size of the drift than the axes can.
    km_px = 1000.0 / sat.gsd * sx
    lo_x, hi_x = axes[0].get_xlim()
    hi_y, lo_y = axes[0].get_ylim()
    x0 = lo_x + 0.05 * (hi_x - lo_x)
    y0 = lo_y + 0.95 * (hi_y - lo_y)
    for ax in axes:
        ax.plot([x0, x0 + km_px], [y0, y0], "-", color="k", lw=1.4, zorder=7)
        ax.text(x0 + km_px / 2, y0 - 0.015 * (hi_y - lo_y), "1 km", ha="center",
                va="bottom", fontsize=6.5, zorder=7)
    fig.tight_layout(pad=0.2)
    fig.savefig(OUT / "fig1_trajectory.pdf", dpi=400, metadata=PDF_META)
    plt.close(fig)
    sat.close()
    print("  fig1_trajectory.pdf")
    return True


def fig2_cdf() -> None:
    """How much of the flight lands under a given error, for each method."""
    pf = np.load(RES / "07_sequential_ana.npz")
    sf = np.load(RES / "05_single_frame.npz")
    vo = np.load(RES / "06_odometry.npz")
    n_tot = len(pf["err"])

    fig, ax = plt.subplots(figsize=(COL, COL * 0.72))
    # Labelled on the curves rather than in a box: at this size a legend large
    # enough to read covers the part of the plot that carries the argument.
    for e, color, name, at, ha in [
        (vo["err"], C_VO, "odometry only", (620, 46), "right"),
        (sf["err"], C_SF, "single-frame\n(77% coverage)", (14, 60), "left"),
        (pf["err"], C_PF, "proposed\n(100% coverage)", (1.4, 72), "left"),
    ]:
        e = np.sort(e[np.isfinite(e)])
        # Denominator is every frame of the flight, not every frame the method
        # answered: a method that declines to answer must pay for that here.
        ax.plot(e, np.arange(1, len(e) + 1) / n_tot * 100, lw=1.3, color=color)
        ax.text(*at, name, color=color, fontsize=6.8, weight="bold",
                ha=ha, va="center", zorder=5,
                bbox=dict(fc="w", ec="none", alpha=0.75, pad=1.0))
    for t in (5, 10, 20):
        ax.axvline(t, color="#999", ls=":", lw=0.6)
        ax.text(t, 2.5, f"{t} m", color="#666", fontsize=6, ha="center")
    ax.set_xscale("log")
    ax.set_xlim(0.5, 5000)
    ax.set_ylim(0, 100)
    ax.set_xlabel("position error (m, log scale)")
    ax.set_ylabel("frames below this error (%)")
    ax.grid(alpha=0.25, which="both", lw=0.4)
    fig.tight_layout(pad=0.2)
    fig.savefig(OUT / "fig2_cdf.pdf", metadata=PDF_META)
    plt.close(fig)
    print("  fig2_cdf.pdf")


def fig3_law() -> None:
    """Match rate predicts final error; altitude does not."""
    d = json.loads((RES / "21_flight_difficulty.json").read_text(encoding="utf-8"))
    ids = sorted(d)
    x = np.array([d[i]["tutma_orani"] * 100 for i in ids])
    y = np.array([d[i]["medyan_hata_m"] for i in ids])
    alt = np.array([d[i]["irtifa_m"] for i in ids])

    fig, ax = plt.subplots(figsize=(COL, COL * 0.78))
    ax.axvspan(0, 50, color=C_VO, alpha=0.06)
    ax.axvspan(50, 100, color=C_PF, alpha=0.06)
    ax.axvline(50, color="#666", ls="--", lw=0.8)

    sc = ax.scatter(x, y, s=22, c=alt, cmap="viridis", edgecolor="k",
                    linewidth=0.4, zorder=3)
    # 06 and 09 sit almost on top of each other; the rest clear to the right.
    nudge = {"09": (-13, -1), "06": (4, -5)}
    for i, fid in enumerate(ids):
        ax.annotate(fid, (x[i], y[i]), fontsize=6, zorder=4,
                    textcoords="offset points", xytext=nudge.get(fid, (4, -1)))

    r = float(np.corrcoef(x, np.log10(y))[0, 1])
    k = np.polyfit(x, np.log10(y), 1)
    xs = np.linspace(5, 100, 60)
    ax.plot(xs, 10 ** np.polyval(k, xs), "--", color="#333", lw=0.8,
            label=f"$\\rho = {r:.3f}$ (log error)")

    cb = fig.colorbar(sc, ax=ax, pad=0.02)
    cb.set_label("flight altitude (m)", fontsize=7)
    cb.ax.tick_params(labelsize=6)
    cb.outline.set_linewidth(0.5)

    ax.set_yscale("log")
    ax.set_xlim(0, 100)
    ax.set_ylim(min(y) * 0.62, max(y) * 2.2)   # headroom: flight 08 sits at the top
    ax.set_xlabel("match rate (%)")
    ax.set_ylabel("median position error (m)")
    ax.grid(alpha=0.25, which="both", lw=0.4)
    ax.legend(loc="lower left", framealpha=0.9, borderpad=0.3, handlelength=1.6)
    fig.tight_layout(pad=0.2)
    fig.savefig(OUT / "fig3_law.pdf", metadata=PDF_META)
    plt.close(fig)
    print("  fig3_law.pdf")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fig2_cdf()
    fig3_law()
    fig1_trajectory()
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

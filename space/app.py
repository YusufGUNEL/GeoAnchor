"""GeoAnchor — an interactive walk through the results.

A README with a table tells you the system works. It does not let you ask
"works where, and how do you know before you fly". That question is the actual
finding of this project, so the demo is built around it: pick a flight, see the
error curve against distance flown, then see the one measurable property that
predicts, in advance, which flights the system will handle.

Everything here is precomputed. No model runs, no GPU, no dataset download --
the Space opens instantly and shows measurements that were made once, on real
flights, and can be traced back to the scripts in the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr
import numpy as np
import plotly.graph_objects as go

ASSETS = Path(__file__).parent / "assets"
REPO = "https://github.com/YusufGUNEL/GeoAnchor"
PAPER = f"{REPO}/blob/main/paper/geoanchor.pdf"

DIFFICULTY = json.loads((ASSETS / "21_flight_difficulty.json").read_text(encoding="utf-8"))
MULTI = json.loads((ASSETS / "20_multiflight.json").read_text(encoding="utf-8"))
FLIGHTS = sorted(f.stem.split("_")[-1] for f in ASSETS.glob("20_flight_[0-9][0-9].npz"))

INK = "#0f172a"
GOOD = "#0ea5e9"
BAD = "#ef4444"
GRID = "rgba(148,163,184,0.25)"


def _layout(fig: go.Figure, title: str, x: str, y: str) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        xaxis_title=x,
        yaxis_title=y,
        template="plotly_white",
        margin=dict(l=60, r=20, t=50, b=50),
        height=430,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def error_curve(flight: str) -> go.Figure:
    """Fused error against odometry-only error, over the distance actually flown.

    Plotted on a log axis because the two are orders of magnitude apart by the
    end of a flight -- which is the whole point, and a linear axis hides it.
    """
    d = np.load(ASSETS / f"20_flight_{flight}.npz")
    dist_km = d["dist"] / 1000.0
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dist_km, y=d["vo_err"], name="visual odometry alone (drifts)",
        line=dict(color=BAD, width=1.6), hovertemplate="%{y:.1f} m<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dist_km, y=d["err"], name="GeoAnchor (fused)",
        line=dict(color=GOOD, width=2.0), hovertemplate="%{y:.1f} m<extra></extra>",
    ))
    fig.update_yaxes(type="log")
    return _layout(fig, f"Flight {flight}: position error along the route",
                   "distance flown (km)", "error (m, log scale)")


def match_curve(flight: str) -> go.Figure:
    """Where the satellite match survives and where it collapses.

    The error curve alone looks like unexplained noise. Put the inlier count
    underneath it and the spikes stop being mysterious: the filter is coasting
    on odometry through terrain the map cannot confirm.
    """
    d = np.load(ASSETS / f"20_flight_{flight}.npz")
    dist_km = d["dist"] / 1000.0
    n = d["n_loftr"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dist_km, y=n, name="matched keypoints", fill="tozeroy",
        line=dict(color=INK, width=1.0), hovertemplate="%{y:.0f}<extra></extra>",
    ))
    fig.add_hline(y=15, line=dict(color=BAD, dash="dash"),
                  annotation_text="below this the frame is rejected")
    return _layout(fig, f"Flight {flight}: how well the camera matched the map",
                   "distance flown (km)", "inlier keypoints")


def stats(flight: str) -> str:
    info = DIFFICULTY.get(flight, {})
    extra = MULTI.get(flight, {})
    med = info.get("medyan_hata_m")
    p90 = info.get("p90_m")
    cov = info.get("kapsama")
    rate = info.get("tutma_orani")
    verdict = ("holds" if (rate or 0) >= 0.5 else "collapses")
    colour = GOOD if (rate or 0) >= 0.5 else BAD
    return f"""
<div style="display:flex;gap:18px;flex-wrap:wrap;margin:6px 0 2px">
  <div><div style="font-size:11px;opacity:.65">MEDIAN ERROR</div>
       <div style="font-size:22px;font-weight:650">{med:.1f} m</div></div>
  <div><div style="font-size:11px;opacity:.65">90th PERCENTILE</div>
       <div style="font-size:22px;font-weight:650">{p90:.0f} m</div></div>
  <div><div style="font-size:11px;opacity:.65">COVERAGE</div>
       <div style="font-size:22px;font-weight:650">{cov * 100:.1f}%</div></div>
  <div><div style="font-size:11px;opacity:.65">MATCH RATE</div>
       <div style="font-size:22px;font-weight:650;color:{colour}">{rate * 100:.0f}% &middot; {verdict}</div></div>
  <div><div style="font-size:11px;opacity:.65">ALTITUDE</div>
       <div style="font-size:22px;font-weight:650">{info.get('irtifa_m', 0):.0f} m</div></div>
  <div><div style="font-size:11px;opacity:.65">ROUTE</div>
       <div style="font-size:22px;font-weight:650">{extra.get('km', 0):.0f} km</div></div>
</div>
<div style="font-size:13px;opacity:.75;margin-top:4px">Flown {info.get('tarih', '?')} &middot;
{extra.get('kare', '?')} frames &middot; ground truth is post-processed GNSS, never shown to the system.</div>
"""


def difficulty_scatter() -> go.Figure:
    """The finding: match rate predicts the outcome, altitude does not.

    Each point is a whole flight. The vertical line at 50% is not fitted -- it
    is where the flights separate, and it is measurable on a planned route
    before anyone takes off.
    """
    xs, ys, names, alts = [], [], [], []
    for fid, info in sorted(DIFFICULTY.items()):
        xs.append(info["tutma_orani"] * 100)
        ys.append(info["medyan_hata_m"])
        alts.append(info["irtifa_m"])
        names.append(f"flight {fid}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text", text=names, textposition="top center",
        textfont=dict(size=10),
        marker=dict(size=[8 + a / 200 for a in alts],
                    color=[GOOD if x >= 50 else BAD for x in xs],
                    line=dict(width=1, color="white")),
        hovertemplate="%{text}<br>match rate %{x:.0f}%<br>median error %{y:.1f} m<extra></extra>",
        showlegend=False,
    ))
    fig.add_vline(x=50, line=dict(color=INK, dash="dash"),
                  annotation_text="50% match rate")
    fig.update_yaxes(type="log")
    fig = _layout(fig, "One property separates the flights that work (marker size = altitude)",
                  "match rate (%)", "median error (m, log scale)")
    fig.add_annotation(x=0.99, y=0.02, xref="paper", yref="paper", showarrow=False,
                       text="correlation between match rate and log error: <b>-0.764</b>",
                       font=dict(size=12), align="right")
    return fig


def table() -> str:
    rows = sorted(DIFFICULTY.items(), key=lambda kv: kv[1]["medyan_hata_m"])
    body = "\n".join(
        f"| {fid} | {MULTI.get(fid, {}).get('kare', '-')} | {i['irtifa_m']:.0f} m | "
        f"{MULTI.get(fid, {}).get('km', 0):.0f} km | {i['tutma_orani'] * 100:.0f}% | "
        f"{i['kapsama'] * 100:.1f}% | **{i['medyan_hata_m']:.2f} m** | {i['p90_m']:.2f} m |"
        for fid, i in rows
    )
    return (
        "| Flight | Frames | Altitude | Distance | Match rate | Coverage | Median | p90 |\n"
        "|---|---|---|---|---|---|---|---|\n" + body
    )


INTRO = f"""
# GeoAnchor — a UAV that finds itself with no GNSS

A drone whose GPS is jammed does not know where it is. Two visual cures exist and
neither works alone: **visual odometry** never stops producing an answer but drifts
(2.8 km off by the end of a 74 km flight), and **matching the camera to a satellite
map** never drifts but fails outright on a quarter of the frames — over water,
uniform farmland, repeating rooftops.

GeoAnchor fuses them in a particle filter. Evaluated on **ten real survey flights**,
406–2572 m altitude, 9–103 km each, 2016–2023. On the seven flights it holds, the
median error is **8–25 m** with position on ≥99.7% of frames. It runs in **1.4 GB of
VRAM**.

The interesting part is not the median. It is that a single measurable property
tells you *in advance* which flights it will handle — and it is not altitude.

[Code and full write-up on GitHub]({REPO}) - [the manuscript]({PAPER})
"""


with gr.Blocks(title="GeoAnchor — GNSS-denied UAV localization") as demo:
    gr.Markdown(INTRO)

    video = ASSETS / "demo.mp4"
    if video.exists():
        gr.Video(str(video), label="Left: UAV camera. Right: live estimate on the map "
                                   "(cyan truth, green estimate, red odometry-only).",
                 autoplay=True, loop=True)

    gr.Markdown("## Walk through a flight")
    picker = gr.Dropdown(FLIGHTS, value="03", label="flight",
                         info="03 is the best case, 08 the worst. Try both.")
    cards = gr.HTML(stats("03"))
    with gr.Row():
        p1 = gr.Plot(error_curve("03"))
    with gr.Row():
        p2 = gr.Plot(match_curve("03"))

    picker.change(lambda f: (stats(f), error_curve(f), match_curve(f)),
                  inputs=picker, outputs=[cards, p1, p2])

    gr.Markdown(
        "## Which flights work, and how you know before flying\n"
        "Each point is an entire flight. Match rate is measured on the planned route "
        "with the true position known — so it can be computed from the satellite map "
        "**before the aircraft leaves the ground**. Altitude is not the discriminator: "
        "the 2572 m flight works, a 551 m one does not."
    )
    gr.Plot(difficulty_scatter())

    gr.Markdown("## Every flight, measured\n" + table())
    gr.Markdown(
        f"Ground truth is post-processed GNSS with 1.5 m cross-track scatter, so the "
        f"reference is clean. Calibration uses the first 20% of each flight, evaluation "
        f"the remaining 80%. The three flights that fail are in the repository too — "
        f"[GeoAnchor on GitHub]({REPO})."
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(primary_hue="sky"))

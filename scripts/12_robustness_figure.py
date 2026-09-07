"""Faz 4 sekli — dayaniklilik egrileri.

Iki panel:
  sol  : olcum kesintisi (uydu eslemesi zorla atiliyor) oranina gore hata
  sag  : goruntu bozulmasi turu ve siddetine gore hata
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.figtext import figdir, num, pick  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIG = figdir()

T = pick({
 "en": {
  "median": "median error", "p90": "90th percentile",
  "x_drop": "measurements forced to be dropped (%)",
  "y_err": "position error (m)",
  "t_drop": ("What if satellite matching is cut off?\n"
             "the remaining fixes degrade as they get sparse"),
  "y_ok20": "frames within 20 m (%)",
  "x_sev": "degradation severity (0 = clean, 1 = severe)",
  "y_med": "median position error (m)",
  "t_deg": ("What if the imagery degrades?\n"
            "fog, darkness, vibration, compression, occlusion, resolution"),
  "base": "undegraded baseline: {} m",
  "hareket bulanikligi": "motion blur", "sis": "fog",
  "dusuk isik": "low light", "jpeg sikistirma": "JPEG compression",
  "kapanma": "occlusion", "cozunurluk kaybi": "resolution loss",
 },
 "tr": {
  "median": "medyan hata", "p90": "%90 dilim",
  "x_drop": "zorla atilan olcum orani (%)",
  "y_err": "konum hatasi (m)",
  "t_drop": ("Uydu eslemesi kesilirse ne olur?\n"
             "Kalan olcumler seyrekleserek azaliyor"),
  "y_ok20": "20 m icinde kalan kare (%)",
  "x_sev": "bozulma siddeti (0 = temiz, 1 = agir)",
  "y_med": "medyan konum hatasi (m)",
  "t_deg": ("Goruntu bozulursa ne olur?\n"
            "sis, gece, titresim, sikistirma, kapanma, cozunurluk"),
  "base": "bozulmasiz temel: {} m",
  "hareket bulanikligi": "hareket bulanikligi", "sis": "sis",
  "dusuk isik": "dusuk isik", "jpeg sikistirma": "jpeg sikistirma",
  "kapanma": "kapanma", "cozunurluk kaybi": "cozunurluk kaybi",
 },
})

C = ["#00ff6a", "#ffb000", "#ff2d55", "#00e5ff", "#c77dff", "#8e8e93"]


def main():
    p = RES / "08_robustness.json"
    if not p.exists():
        print("results/08_robustness.json yok - once 08_robustness.py calistir")
        return
    R = json.loads(p.read_text(encoding="utf-8"))

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    # --- sol: olcum kesintisi ---
    ax = axes[0]
    keys = sorted(R["olcum_kesintisi"].keys(), key=lambda k: int(k.rstrip("%")))
    x = [int(k.rstrip("%")) for k in keys]
    med = [R["olcum_kesintisi"][k]["medyan_m"] for k in keys]
    p90 = [R["olcum_kesintisi"][k]["p90_m"] for k in keys]
    ok20 = [R["olcum_kesintisi"][k]["basari_20m"] * 100 for k in keys]
    ax.plot(x, med, "o-", lw=2.2, ms=7, color=C[0], label=T["median"])
    ax.plot(x, p90, "s--", lw=1.8, ms=6, color=C[1], label=T["p90"])
    ax.set_xlabel(T["x_drop"])
    ax.set_ylabel(T["y_err"])
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.set_title(T["t_drop"], fontsize=12)
    ax2 = ax.twinx()
    ax2.plot(x, ok20, "^:", lw=1.5, ms=6, color=C[3], alpha=0.85)
    ax2.set_ylabel(T["y_ok20"], color=C[3])
    ax2.tick_params(axis="y", colors=C[3])
    ax2.set_ylim(0, 100)
    ax.legend(fontsize=10, loc="upper left")

    # --- sag: goruntu bozulmasi ---
    ax = axes[1]
    groups = {}
    for tag, s in R["bozulma"].items():
        name, sev = tag.rsplit("_", 1)
        groups.setdefault(name.replace("_", " "), []).append((int(sev) / 100, s))
    base = R["olcum_kesintisi"].get("0%", {}).get("medyan_m", np.nan)
    if np.isfinite(base):
        ax.axhline(base, color="#666", ls=":", lw=1.4)
        ax.text(0.02, base * 1.06, T["base"].format(num(base, 1)),
                color="#555", fontsize=9)
    for i, (name, vals) in enumerate(sorted(groups.items())):
        vals.sort()
        xs = [0.0] + [v[0] for v in vals]
        ys = [base] + [v[1]["medyan_m"] for v in vals]
        ax.plot(xs, ys, "o-", lw=2.0, ms=6, color=C[i % len(C)],
                label=T.get(name, name))
    ax.set_xlabel(T["x_sev"])
    ax.set_ylabel(T["y_med"])
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.set_title(T["t_deg"], fontsize=12)
    ax.legend(fontsize=9, ncol=2)

    fig.tight_layout()
    out = FIG / "14_dayaniklilik.png"
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"{out.relative_to(ROOT)} yazildi")


if __name__ == "__main__":
    main()

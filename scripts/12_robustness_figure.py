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

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

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
    ax.plot(x, med, "o-", lw=2.2, ms=7, color=C[0], label="medyan hata")
    ax.plot(x, p90, "s--", lw=1.8, ms=6, color=C[1], label="%90 dilim")
    ax.set_xlabel("zorla atilan olcum orani (%)")
    ax.set_ylabel("konum hatasi (m)")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.set_title("Uydu eslemesi kesilirse ne olur?\n"
                 "Kalan olcumler seyrekleserek azaliyor", fontsize=12)
    ax2 = ax.twinx()
    ax2.plot(x, ok20, "^:", lw=1.5, ms=6, color=C[3], alpha=0.85)
    ax2.set_ylabel("20 m icinde kalan kare (%)", color=C[3])
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
        ax.text(0.02, base * 1.06, "bozulmasiz temel: {:.1f} m".format(base),
                color="#555", fontsize=9)
    for i, (name, vals) in enumerate(sorted(groups.items())):
        vals.sort()
        xs = [0.0] + [v[0] for v in vals]
        ys = [base] + [v[1]["medyan_m"] for v in vals]
        ax.plot(xs, ys, "o-", lw=2.0, ms=6, color=C[i % len(C)], label=name)
    ax.set_xlabel("bozulma siddeti (0 = temiz, 1 = agir)")
    ax.set_ylabel("medyan konum hatasi (m)")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.set_title("Goruntu bozulursa ne olur?\n"
                 "sis, gece, titresim, sikistirma, kapanma, cozunurluk",
                 fontsize=12)
    ax.legend(fontsize=9, ncol=2)

    fig.tight_layout()
    fig.savefig(FIG / "14_dayaniklilik.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("figures/14_dayaniklilik.png yazildi")


if __name__ == "__main__":
    main()

"""Ucus zorlugu sekli — esleme orani ile nihai hata iliskisi.

Onceki surum x eksenine "medyan ic nokta" koyuyordu; iki ucusun medyani sifir
oldugu icin logaritmik eksende gorunmuyorlardi. Esleme orani hem sifir sorunu
yasatmiyor hem de daha guclu bir yordayici (korelasyon -0,765 vs -0,693).
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
d = json.loads((ROOT / "results" / "21_flight_difficulty.json").read_text(encoding="utf-8"))

ids = sorted(d)
x = np.array([d[i]["tutma_orani"] * 100 for i in ids])
y = np.array([d[i]["medyan_hata_m"] for i in ids])
alt = np.array([d[i]["irtifa_m"] for i in ids])
ok = x >= 50

fig, ax = plt.subplots(figsize=(10, 6.8))
ax.axvspan(0, 50, color="#ff2d55", alpha=0.07)
ax.axvspan(50, 100, color="#00b894", alpha=0.07)
ax.axvline(50, color="#636e72", ls="--", lw=1.4)
ax.text(51, 430, "esik: %50", color="#636e72", fontsize=10)
ax.text(3, 15, "esleme orani dusuk\nsistem cokuyor", color="#c0392b",
        fontsize=11, weight="bold")
ax.text(53, 220, "esleme orani yeterli\n8 - 25 m arasi", color="#0e8f6f",
        fontsize=11, weight="bold")

sc = ax.scatter(x, y, s=90 + alt / 10, c=alt, cmap="viridis",
                edgecolor="k", zorder=3, linewidth=0.8)
for i, fid in enumerate(ids):
    ax.annotate("  " + fid, (x[i], y[i]), fontsize=11, va="center", zorder=4)

r = float(np.corrcoef(x, np.log10(y))[0, 1])
k = np.polyfit(x, np.log10(y), 1)
xs = np.linspace(5, 100, 60)
ax.plot(xs, 10 ** np.polyval(k, xs), "--", color="#2d3436", lw=1.4,
        label="egilim (korelasyon %.2f)" % r)

cb = fig.colorbar(sc, ax=ax, pad=0.02)
cb.set_label("ucus irtifasi (m)")
ax.set_yscale("log")
ax.set_xlim(0, 100)
ax.set_xlabel("esleme orani (%)\n"
              "gercek konum biliniyorken uydu haritasiyla eslesebilen kare orani")
ax.set_ylabel("nihai medyan konum hatasi (m)")
ax.set_title("Basarimi belirleyen sey algoritma degil, VERININ HARITAYLA ORTUSMESI\n"
             "Her nokta bir ucus; renk irtifayi gosteriyor", fontsize=13)
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=10, loc="upper right")
fig.tight_layout()
fig.savefig(ROOT / "figures" / "15_ucus_zorlugu.png", dpi=130, bbox_inches="tight")
plt.close(fig)
print("figures/15_ucus_zorlugu.png yeniden yazildi (%d ucus)" % len(ids))
print("  esik ustu: %s" % " ".join(np.array(ids)[ok]))
print("  esik alti: %s" % " ".join(np.array(ids)[~ok]))

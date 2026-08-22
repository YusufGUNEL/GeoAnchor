"""Ucuslar arasi basarim farki neden kaynaklaniyor?

Cok ucuslu degerlendirmede sonuclar 8 m ile 648 m arasinda dagildi. Soru su:
sistem bazi ucuslarda mi kotu calisiyor, yoksa bazi ucuslarin verisi mi
eslesmeye elverissiz?

Olcut: GERCEK KONUM BILINIYORKEN elde edilen ic nokta sayisi. Bu, algoritmadan
bagimsiz olarak "bu ucusun goruntuleri bu uydu haritasiyla ne kadar
ortusuyor" sorusunun cevabidir. Konum aramasi devrede degil, dogru yere
bakiyoruz; tutmuyorsa sebep veridir.

Eger nihai hata bu olcutle aciklanabiliyorsa, sistem verinin izin verdigi
kadar iyi demektir — ve bir ucus oncesinde harita uzerinde bu olcum yapilarak
sistemin o gorevde ise yarayip yaramayacagi ONCEDEN kestirilebilir.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.flight import load_flight
from src.geo import SatelliteMap
from src.matching import LoFTRMatcher

DATA = r"D:\GeoAnchorData\full"
CACHE = Path(r"D:\GeoAnchorData\cache_multi")
ROOT = Path(__file__).resolve().parents[1]
N_SAMPLE = 30


def measure(fid: str, matcher: LoFTRMatcher) -> dict:
    flight = load_flight(DATA, fid)
    sat = SatelliteMap(flight.satellite_path)
    p = CACHE / f"northup_{fid}_640.npy"
    if not p.exists():
        sat.close()
        return {}
    q = np.load(p, mmap_mode="r")
    idxs = np.linspace(0, flight.n_frames - 1, N_SAMPLE).astype(int)
    inl, nmt = [], []
    for i in idxs:
        r = flight.df.iloc[i]
        if not sat.contains(float(r.lat), float(r.lon)):
            continue
        crop, _, _, _ = sat.crop_meters(float(r.lat), float(r.lon), 400.0, 640)
        pa, pb, _ = matcher.match(
            cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY),
            cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY))
        nmt.append(len(pa))
        n = 0
        if len(pa) >= 30:
            H, mask = cv2.findHomography(pa.astype(np.float32),
                                         pb.astype(np.float32),
                                         cv2.USAC_MAGSAC, 4.0,
                                         maxIters=10_000, confidence=0.999)
            if mask is not None:
                n = int(mask.sum())
        inl.append(n)
    sat.close()
    if not inl:
        return {}
    inl = np.array(inl)
    return {"medyan_ic_nokta": float(np.median(inl)),
            "tutma_orani": float((inl >= 40).mean()),
            "medyan_eslesme": float(np.median(nmt)),
            "tarih": str(flight.df["date"].iloc[0])[:10],
            "n_ornek": int(len(inl))}


def main():
    mf = json.loads((ROOT / "results" / "20_multiflight.json").read_text(encoding="utf-8"))
    matcher = LoFTRMatcher(size=640)
    out = {}
    print("%-5s %8s %14s %12s %10s %10s" % (
        "ucus", "tarih", "medyan ic nokta", "tutma", "medyan hata", "kapsama"))
    print("-" * 66)
    for fid in sorted(mf.keys()):
        r = mf[fid]
        if r.get("durum") != "tamam":
            continue
        m = measure(fid, matcher)
        if not m:
            continue
        m["medyan_hata_m"] = r["medyan_m"]
        m["kapsama"] = r["kapsama"]
        m["p90_m"] = r["p90_m"]
        m["irtifa_m"] = r["irtifa_m"]
        out[fid] = m
        print("%-5s %8s %14.0f %11.0f%% %9.2fm %9.1f%%" % (
            fid, m["tarih"], m["medyan_ic_nokta"], m["tutma_orani"] * 100,
            m["medyan_hata_m"], m["kapsama"] * 100), flush=True)

    (ROOT / "results" / "21_flight_difficulty.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    if len(out) >= 4:
        x = np.array([v["medyan_ic_nokta"] for v in out.values()])
        y = np.array([v["medyan_hata_m"] for v in out.values()])
        lx, ly = np.log10(np.maximum(x, 1)), np.log10(y)
        rho = float(np.corrcoef(lx, ly)[0, 1])
        print("\nlog-log korelasyon: %.3f" % rho)

        fig, ax = plt.subplots(figsize=(9, 6.5))
        ax.scatter(x, y, s=140, c="#00b894", edgecolor="k", zorder=3)
        for fid, v in out.items():
            ax.annotate(" " + fid, (v["medyan_ic_nokta"], v["medyan_hata_m"]),
                        fontsize=11, va="center")
        if len(x) >= 3:
            k = np.polyfit(lx, ly, 1)
            xs = np.logspace(np.log10(max(1, x.min() * 0.7)),
                             np.log10(x.max() * 1.4), 50)
            ax.plot(xs, 10 ** np.polyval(k, np.log10(xs)), "--",
                    color="#636e72", lw=1.5,
                    label="egilim (log-log korelasyon %.2f)" % rho)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("gercek konumda medyan ic nokta\n"
                      "(verinin haritayla ne kadar ortustugu)")
        ax.set_ylabel("nihai medyan konum hatasi (m)")
        ax.set_title("Basarim algoritmadan degil VERIDEN belirleniyor\n"
                     "Her nokta bir ucus", fontsize=13)
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=10)
        fig.tight_layout()
        fig.savefig(ROOT / "figures" / "15_ucus_zorlugu.png", dpi=130,
                    bbox_inches="tight")
        plt.close(fig)
        print("figures/15_ucus_zorlugu.png yazildi")


if __name__ == "__main__":
    main()

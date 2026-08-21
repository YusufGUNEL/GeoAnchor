"""Faz 1 — tüm uçuşta tek kare mutlak konumlandırma (haritanın tamamında arama).

Bu, karşılaştırma tabanıdır: her kare bağımsız işlenir, geçmiş bilgisi yok.
Faz 3'teki sıralı füzyon bunun üstüne kurulacak ve farkı burada görülecek.
"""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m
from src.geometry import AttitudeModel
from src.matching import LoFTRMatcher
from src.localize import SingleFrameLocalizer

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
# Faz 1b kalibrasyonundan (uçuşun ilk %20'si üzerinden)
ATT = AttitudeModel(pitch_bias_deg=2.006, roll_bias_deg=-0.137)


def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    qe = np.load(CACHE / "query_emb_448.npy")
    g = np.load(CACHE / "tilegrid_03.npz")
    te = np.load(CACHE / "tile_emb_448.npy")
    matcher = LoFTRMatcher(size=640)
    loc = SingleFrameLocalizer(sat, g["lat"], g["lon"], te, matcher, ATT)

    n = flight.n_frames
    keys = ["lat", "lon", "err", "inliers", "n_tried", "rank", "scale", "ms"]
    out = {k: np.full(n, np.nan) for k in keys}

    t_start = time.time()
    for i in range(n):
        r = flight.df.iloc[i]
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        t0 = time.time()
        f = loc.localize(qg, qe[i], pitch=float(r.Kappa), roll=float(r.Omega),
                         height=float(r.height), yaw=float(r.Phi1))
        out["ms"][i] = (time.time() - t0) * 1000
        out["n_tried"][i] = f.n_tried
        if f.ok:
            out["lat"][i] = f.lat
            out["lon"][i] = f.lon
            out["err"][i] = haversine_m(float(r.lat), float(r.lon), f.lat, f.lon)
            out["inliers"][i] = f.inliers
            out["rank"][i] = f.cand_rank
            out["scale"][i] = f.scale
        if (i + 1) % 50 == 0:
            done = out["err"][:i + 1]
            ok = np.isfinite(done)
            el = time.time() - t_start
            print(f"  {i+1}/{n}  tutan %{ok.mean()*100:.0f}  "
                  f"medyan {np.nanmedian(done):.1f} m  "
                  f"{el/60:.1f} dk gecti, ~{el/(i+1)*(n-i-1)/60:.1f} dk kaldi",
                  flush=True)

    np.savez(ROOT / "results" / "05_single_frame.npz", **out)

    e = out["err"][np.isfinite(out["err"])]
    ok_rate = len(e) / n
    summary = {
        "n": n,
        "cozulen": int(len(e)),
        "cozum_orani": float(ok_rate),
        "medyan_m": float(np.median(e)),
        "ortalama_m": float(e.mean()),
        "p90_m": float(np.percentile(e, 90)),
        "buyuk_iska_100m": int((e > 100).sum()),
        "ort_ms": float(np.nanmean(out["ms"])),
        "ort_aday": float(np.nanmean(out["n_tried"])),
    }
    for t in [1, 3, 5, 10, 20, 50]:
        summary[f"basari_{t}m"] = float((e <= t).mean() * ok_rate)

    print("\n=== FAZ 1: TEK KARE (haritanin tamaminda arama) ===")
    print(f"  cozulen kare      : {len(e)}/{n} (%{ok_rate*100:.1f})")
    print(f"  medyan hata       : {np.median(e):.2f} m   (sadece cozulenlerde)")
    print(f"  ortalama hata     : {e.mean():.2f} m")
    print(f"  %90 dilim         : {np.percentile(e,90):.2f} m")
    print(f"  buyuk iska (>100m): {(e>100).sum()} kare")
    print("  TUM karelerde basari orani (cozulemeyen = basarisiz):")
    for t in [1, 3, 5, 10, 20, 50]:
        print(f"    {t:>2} m icinde   : %{(e<=t).mean()*ok_rate*100:5.1f}")
    print(f"  kare basina sure  : {np.nanmean(out['ms']):.0f} ms "
          f"(ortalama {np.nanmean(out['n_tried']):.1f} aday denendi)")
    print(f"  toplam            : {(time.time()-t_start)/60:.1f} dk")

    (ROOT / "results" / "05_single_frame.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    sat.close()


if __name__ == "__main__":
    main()

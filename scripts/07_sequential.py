"""Faz 3 — sıralı konumlandırma çalıştırması (projenin çekirdek sonucu).

Karşılaştırma:
  Faz 1 (tek kare)  : her kare bağımsız, haritanın tamamında arama
  Faz 2 (odometri)  : sürekli ama sürükleniyor
  Faz 3 (füzyon)    : sürekli VE sürüklenmesiz, üstelik daha az eşleme çağrısı
"""
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from src.flight import load_flight
from src.geo import SatelliteMap, latlon_to_local_m
from src.geometry import AttitudeModel
from src.matching import LoFTRMatcher
from src.localize import SingleFrameLocalizer
from src.particle_filter import PFConfig
from src.sequential import SequentialLocalizer

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
ATT = AttitudeModel(pitch_bias_deg=2.006, roll_bias_deg=-0.137)


def run(drop_rate=0.0, seed=0, n_particles=600, tag="ana", verbose=True,
        degrade=None, max_frames=None, use_online_yaw=True):
    """drop_rate: ölçümlerin bu oranı zorla atılır (reddedilme senaryosu)."""
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    qe = np.load(CACHE / "query_emb_448.npy")
    g = np.load(CACHE / "tilegrid_03.npz")
    te = np.load(CACHE / "tile_emb_448.npy")
    odo = np.load(ROOT / "results" / "06b_odometry_cal.npz")
    odo_raw = np.load(ROOT / "results" / "06_odometry.npz")

    matcher = LoFTRMatcher(size=640)
    loc = SingleFrameLocalizer(sat, g["lat"], g["lon"], te, matcher, ATT)
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    seq = SequentialLocalizer(sat, loc, ATT, lat0, lon0,
                              pf_cfg=PFConfig(n_particles=n_particles),
                              use_online_yaw=use_online_yaw, seed=seed)

    n = flight.n_frames if max_frames is None else min(max_frames, flight.n_frames)
    rng = np.random.default_rng(seed + 1000)
    out = {k: np.full(n, np.nan) for k in
           ["north", "east", "err", "spread", "n_loftr", "inliers", "ms",
            "yaw_bias", "scale_corr", "meas_north", "meas_east", "pred_north", "pred_east"]}
    modes = []

    # HAM odometri kullaniliyor: pusula sapmasini sistemin KENDISI
    # harita eslemelerinden ogrenecek (gercek konum kullanmadan).
    dn_all = odo_raw["d_north"]
    de_all = odo_raw["d_east"]
    gt_n = d["north_m"].values
    gt_e = d["east_m"].values

    t_start = time.time()
    for i in range(n):
        r = d.iloc[i]
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        if degrade is not None:
            qg = degrade(qg, rng)
        dn = de = None
        if i > 0 and np.isfinite(dn_all[i - 1]):
            dn, de = float(dn_all[i - 1]), float(de_all[i - 1])

        t0 = time.time()
        if drop_rate > 0 and i > 0 and rng.random() < drop_rate:
            # olcum reddedildi: sadece tahmin
            if seq.pf.initialized:
                if dn is not None:
                    rdn, rde = seq._rotate_step(dn, de)
                    seq.pf.predict(rdn, rde)
                    seq.last_step = (rdn, rde)
                    seq._note_motion(rdn, rde, float(r.Phi1))
                else:
                    seq.pf.dead_reckon(*seq._dr_step(float(r.Phi1)))
                nn, ee = seq.pf.estimate()
                res = type("R", (), {})()
                res.north, res.east = nn, ee
                res.spread = seq.pf.spread()
                res.n_loftr, res.inliers, res.mode = 0, 0, "olcum reddedildi"
                res.yaw_bias = seq.yaw_bias
                seq.pf.no_meas_count += 1
            else:
                res = seq.step(qg, qe[i], float(r.Kappa), float(r.Omega),
                               float(r.height), float(r.Phi1), dn, de)
        else:
            res = seq.step(qg, qe[i], float(r.Kappa), float(r.Omega),
                           float(r.height), float(r.Phi1), dn, de)
        out["ms"][i] = (time.time() - t0) * 1000
        out["north"][i], out["east"][i] = res.north, res.east
        out["spread"][i] = res.spread
        out["n_loftr"][i] = res.n_loftr
        out["inliers"][i] = res.inliers
        out["yaw_bias"][i] = getattr(res, "yaw_bias", np.nan)
        for k in ("scale_corr", "meas_north", "meas_east", "pred_north", "pred_east"):
            out[k][i] = getattr(res, k, np.nan)
        modes.append(res.mode)
        if np.isfinite(res.north):
            out["err"][i] = float(np.hypot(res.north - gt_n[i], res.east - gt_e[i]))
        if verbose and (i + 1) % 50 == 0:
            el = time.time() - t_start
            print(f"  {i+1}/{n}  medyan {np.nanmedian(out['err'][:i+1]):.1f} m  "
                  f"LoFTR/kare {np.nanmean(out['n_loftr'][:i+1]):.2f}  "
                  f"{el/60:.1f} dk gecti, ~{el/(i+1)*(n-i-1)/60:.1f} dk kaldi",
                  flush=True)

    e = out["err"][np.isfinite(out["err"])]
    summary = {
        "etiket": tag, "n": int(n), "drop_rate": drop_rate, "seed": seed,
        "n_particles": n_particles,
        "kapsama": float(len(e) / n),
        "medyan_m": float(np.median(e)), "ortalama_m": float(e.mean()),
        "p90_m": float(np.percentile(e, 90)), "max_m": float(e.max()),
        "ate_m": float(np.sqrt((e ** 2).mean())),
        "loftr_per_frame": float(np.nanmean(out["n_loftr"])),
        "ms_per_frame": float(np.nanmean(out["ms"])),
        "yeniden_konumlanma": int(sum(1 for m in modes if m == "yeniden konumlanma")),
        "sadece_odometri": int(sum(1 for m in modes if m == "sadece odometri")),
    }
    for t in [1, 3, 5, 10, 20, 50]:
        summary[f"basari_{t}m"] = float((e <= t).mean() * len(e) / n)

    np.savez(ROOT / "results" / f"07_sequential_{tag}.npz",
             modes=np.array(modes), **out)
    sat.close()
    return summary, out, modes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="ana")
    ap.add_argument("--drop", type=float, default=0.0)
    ap.add_argument("--particles", type=int, default=600)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-online-yaw", action="store_true")
    ap.add_argument("--max-frames", type=int, default=None)
    a = ap.parse_args()

    s, out, modes = run(drop_rate=a.drop, seed=a.seed, n_particles=a.particles,
                        tag=a.tag, max_frames=a.max_frames,
                        use_online_yaw=not a.no_online_yaw)
    print(f"\n=== FAZ 3: SIRALI FUZYON ({a.tag}) ===")
    print(f"  kapsama (konum uretilen kare) : %{s['kapsama']*100:.1f}")
    print(f"  medyan hata                   : {s['medyan_m']:.2f} m")
    print(f"  ortalama hata                 : {s['ortalama_m']:.2f} m")
    print(f"  %90 dilim                     : {s['p90_m']:.2f} m")
    print(f"  en buyuk hata                 : {s['max_m']:.2f} m")
    print(f"  ATE (karekok ortalama)        : {s['ate_m']:.2f} m")
    print("  basari orani (tum kareler):")
    for t in [1, 3, 5, 10, 20, 50]:
        print(f"    {t:>2} m icinde                : %{s[f'basari_{t}m']*100:5.1f}")
    print(f"  kare basina LoFTR cagrisi     : {s['loftr_per_frame']:.2f}")
    print(f"  kare basina sure              : {s['ms_per_frame']:.0f} ms")
    print(f"  yeniden konumlanma            : {s['yeniden_konumlanma']} kare")
    print(f"  sadece odometri (olcumsuz)    : {s['sadece_odometri']} kare")

    p = ROOT / "results" / f"07_sequential_{a.tag}.json"
    p.write_text(json.dumps(s, indent=2), encoding="utf-8")
    print(f"\n{p.name} yazildi")


if __name__ == "__main__":
    main()

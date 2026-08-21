"""Faz 5 — ablasyon: sistemin hangi parcasi ne kadar ise yariyor?

Her satir, tam sistemden tek bir bileseni cikararak elde edilir. Amac
"her sey onemliydi" demek degil; hangisinin gercekten fark yarattigini,
hangisinin sus oldugunu SAYIYLA gostermek.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import cv2

from src.flight import load_flight
from src.geo import SatelliteMap
from src.geometry import AttitudeModel
from src.matching import LoFTRMatcher
from src.localize import SingleFrameLocalizer
from src.particle_filter import PFConfig
from src.sequential import SequentialLocalizer

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
ATT = AttitudeModel(pitch_bias_deg=2.006, roll_bias_deg=-0.137)
N_FRAMES = 300


def run_variant(name, n_frames=N_FRAMES, pf_kw=None, seq_kw=None,
                attitude=ATT, use_odometry=True):
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    qe = np.load(CACHE / "query_emb_448.npy")
    g = np.load(CACHE / "tilegrid_03.npz")
    te = np.load(CACHE / "tile_emb_448.npy")
    odo = np.load(ROOT / "results" / "06_odometry.npz")

    matcher = LoFTRMatcher(size=640)
    loc = SingleFrameLocalizer(sat, g["lat"], g["lon"], te, matcher, attitude)
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    seq = SequentialLocalizer(sat, loc, attitude, lat0, lon0,
                              pf_cfg=PFConfig(**(pf_kw or {})),
                              seed=0, **(seq_kw or {}))

    n = min(n_frames, flight.n_frames)
    gt_n, gt_e = d["north_m"].values, d["east_m"].values
    dn_all, de_all = odo["d_north"], odo["d_east"]
    err = np.full(n, np.nan)
    nl = np.zeros(n)
    t0 = time.time()
    for i in range(n):
        r = d.iloc[i]
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        dn = de = None
        if use_odometry and i > 0 and np.isfinite(dn_all[i - 1]):
            dn, de = float(dn_all[i - 1]), float(de_all[i - 1])
        res = seq.step(qg, qe[i], float(r.Kappa), float(r.Omega),
                       float(r.height), float(r.Phi1), dn, de)
        nl[i] = res.n_loftr
        if np.isfinite(res.north):
            err[i] = float(np.hypot(res.north - gt_n[i], res.east - gt_e[i]))
    sat.close()
    e = err[np.isfinite(err)]
    return {
        "ad": name, "kapsama": float(len(e) / n),
        "medyan_m": float(np.median(e)), "ortalama_m": float(e.mean()),
        "p90_m": float(np.percentile(e, 90)), "max_m": float(e.max()),
        "ate_m": float(np.sqrt((e ** 2).mean())),
        "basari_10m": float((e <= 10).mean() * len(e) / n),
        "basari_20m": float((e <= 20).mean() * len(e) / n),
        "loftr_per_frame": float(nl.mean()),
        "sure_dk": float((time.time() - t0) / 60),
    }


def main():
    variants = [
        ("tam sistem", {}, {}, ATT, True),
        ("cevrimici pusula kalibrasyonu YOK", {}, {"use_online_yaw": False}, ATT, True),
        ("cevrimici olcek kalibrasyonu YOK", {}, {"use_online_scale": False}, ATT, True),
        ("parcacik enjeksiyonu YOK", {"inject_frac": 0.0}, {}, ATT, True),
        ("durus (boresight) duzeltmesi YOK", {}, {}, AttitudeModel(0.0, 0.0), True),
        ("odometri YOK (sadece olcum)", {}, {}, ATT, False),
        ("100 parcacik", {"n_particles": 100}, {}, ATT, True),
        ("2000 parcacik", {"n_particles": 2000}, {}, ATT, True),
        ("aykiri deger tabani YOK", {"outlier_floor": 0.0}, {}, ATT, True),
    ]
    out = []
    print(f"{'varyant':>36} {'kapsama':>8} {'medyan':>9} {'p90':>9} "
          f"{'en buyuk':>10} {'ATE':>9} {'<=20m':>7} {'LoFTR':>6}")
    print("-" * 100)
    for name, pf_kw, seq_kw, att, use_odo in variants:
        s = run_variant(name, pf_kw=pf_kw, seq_kw=seq_kw,
                        attitude=att, use_odometry=use_odo)
        out.append(s)
        print(f"{name:>36} %{s['kapsama']*100:6.1f} {s['medyan_m']:8.2f}m "
              f"{s['p90_m']:8.2f}m {s['max_m']:9.1f}m {s['ate_m']:8.2f}m "
              f"%{s['basari_20m']*100:5.1f} {s['loftr_per_frame']:6.2f}", flush=True)

    (ROOT / "results" / "11_ablation.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nresults/11_ablation.json yazildi")


if __name__ == "__main__":
    main()

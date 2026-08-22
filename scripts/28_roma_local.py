"""RoMa'yi SADECE tahmin edilen yerin cevresinde kullanmak ise yarar mi?

Bulgu: RoMa kuresel aramada guvenilmez (yanlis yere de eslesiyor). Ama sirali
sistemde nerede oldugumuzu kabaca biliyoruz ve kapi uzak sonuclari zaten
eliyor. Belki orada kullanilabilir.

Bu betik iki ucusta karsilastirir: LoFTR'in iyi calistigi 01 ve tamamen
coktugu 08.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap
from src.geometry import AttitudeModel
from src.matching import LoFTRMatcher, RomaMatcher
from src.localize import SingleFrameLocalizer
from src.particle_filter import PFConfig
from src.sequential import SequentialLocalizer
from src import pipeline as P

DATA = r"D:\GeoAnchorData\full"
CACHE = Path(r"D:\GeoAnchorData\cache_multi")
ROOT = Path(__file__).resolve().parents[1]
N_FRAMES = 220


def run(fid, matcher, gray, min_inl, ratio, tag):
    flight = load_flight(DATA, fid)
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / f"northup_{fid}_640.npy", mmap_mode="r")
    qe = np.load(CACHE / f"qemb_{fid}.npy")
    z = np.load(CACHE / f"tiles_{fid}.npz")
    odo = np.load(ROOT / "results" / f"20_flight_{fid}.npz") if False else None
    gsd = P.estimate_drone_gsd(flight)
    att, _, _, _ = P.calibrate_boresight(flight, sat, q, LoFTRMatcher(size=640), gsd)
    dn, de = P.run_odometry(q, gsd, flight)

    loc = SingleFrameLocalizer(sat, z["lat"], z["lon"], z["emb"], matcher, att,
                               min_inliers=min_inl, accept_ratio=ratio,
                               early_exit=max(min_inl * 4, 200))
    d = flight.df
    seq = SequentialLocalizer(sat, loc, att, float(d["lat"].iloc[0]),
                              float(d["lon"].iloc[0]), pf_cfg=PFConfig(),
                              local_min_inliers=min_inl, seed=0)
    n = min(N_FRAMES, flight.n_frames)
    gt_n, gt_e = d["north_m"].values, d["east_m"].values
    err = np.full(n, np.nan); nl = np.zeros(n)
    t0 = time.time()
    for i in range(n):
        r = d.iloc[i]
        qi = np.ascontiguousarray(q[i])
        qg = cv2.cvtColor(qi, cv2.COLOR_RGB2GRAY) if gray else qi
        a = b = None
        if i > 0 and np.isfinite(dn[i-1]):
            a, b = float(dn[i-1]), float(de[i-1])
        res = seq.step(qg, qe[i], float(r.Kappa), float(r.Omega),
                       float(r.height), float(r.Phi1), a, b)
        nl[i] = res.n_loftr
        if np.isfinite(res.north):
            err[i] = float(np.hypot(res.north - gt_n[i], res.east - gt_e[i]))
    sat.close()
    e = err[np.isfinite(err)]
    return {"etiket": tag, "ucus": fid, "kapsama": float(len(e)/n),
            "medyan_m": float(np.median(e)) if len(e) else float("nan"),
            "p90_m": float(np.percentile(e,90)) if len(e) else float("nan"),
            "max_m": float(e.max()) if len(e) else float("nan"),
            "cagri": float(nl.mean()), "sn_kare": float((time.time()-t0)/n)}


def main():
    out = []
    print("%-8s %-26s %8s %9s %9s %9s %7s" % ("ucus","yapilandirma","kapsama","medyan","p90","en buyuk","sn/kare"))
    print("-"*84)
    for fid in ["01","08"]:
        m = LoFTRMatcher(size=640)
        r = run(fid, m, True, 40, 0.0, "LoFTR (mevcut)")
        out.append(r); del m
        import torch; torch.cuda.empty_cache()
        print("%-8s %-26s %%%6.1f %8.2fm %8.2fm %8.1fm %7.2f" % (fid, r["etiket"], r["kapsama"]*100, r["medyan_m"], r["p90_m"], r["max_m"], r["sn_kare"]), flush=True)
        m = RomaMatcher()
        for min_inl, ratio, tag in [(3050, 0.0, "RoMa (ham esik 3050)"),
                                    (500, 0.61, "RoMa (oran esigi 0.61)")]:
            r = run(fid, m, False, min_inl, ratio, tag)
            out.append(r)
            print("%-8s %-26s %%%6.1f %8.2fm %8.2fm %8.1fm %7.2f" % (fid, r["etiket"], r["kapsama"]*100, r["medyan_m"], r["p90_m"], r["max_m"], r["sn_kare"]), flush=True)
        del m; torch.cuda.empty_cache()
    (ROOT/"results"/"28_roma_local.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nresults/28_roma_local.json yazildi")


if __name__ == "__main__":
    main()

"""Bulaniklik dayanikliligi duzeltmesinin olculmesi.

Faz 4'te agir titresim bulanikliginda sistem cokuyordu (medyan 6,6 -> 58,3 m).
Iki care denenmisti:
  A) keskinlik kapisi   : kare komsularindan belirgin bulaniksa eslemeye SOKMA
  B) alan esitleme      : uydu karosunu sorgu kadar bulaniklastir
     (bulaniklik miktari uydu karosunun kendi keskinligine gore olculur —
      mutlak referans gerekmiyor)

Iki senaryo ayri ayri olculur, cunku carelerin gecerlilik alanlari farkli:
  SENARYO 1 (her kare bulanik)   : A ise yaramaz, B yaramali
  SENARYO 2 (arada bir bulanik)  : A yaramali
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np

from src.flight import load_flight
from src.geo import SatelliteMap
from src.geometry import AttitudeModel
from src.matching import LoFTRMatcher
from src.localize import SingleFrameLocalizer
from src.particle_filter import PFConfig
from src.sequential import SequentialLocalizer
from src.degrade import motion_blur

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
ATT = AttitudeModel(pitch_bias_deg=2.006, roll_bias_deg=-0.137)
N = 300


def run(gate: bool, blur_match: bool, severity: float, mode: str, seed: int = 0):
    """mode: 'her' (tum kareler bulanik) | 'arada' (her 6. kare bulanik)"""
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    qe = np.load(CACHE / "query_emb_448.npy")
    g = np.load(CACHE / "tilegrid_03.npz")
    te = np.load(CACHE / "tile_emb_448.npy")
    odo = np.load(ROOT / "results" / "06_odometry.npz")

    matcher = LoFTRMatcher(size=640)
    loc = SingleFrameLocalizer(sat, g["lat"], g["lon"], te, matcher, ATT)
    d = flight.df
    lat0, lon0 = float(d["lat"].iloc[0]), float(d["lon"].iloc[0])
    seq = SequentialLocalizer(sat, loc, ATT, lat0, lon0, pf_cfg=PFConfig(),
                              use_sharpness_gate=gate, use_blur_matching=blur_match,
                              seed=seed)

    rng = np.random.default_rng(seed + 7)
    gt_n, gt_e = d["north_m"].values, d["east_m"].values
    dn_all, de_all = odo["d_north"], odo["d_east"]
    err = np.full(N, np.nan)
    nl = np.zeros(N)
    skipped = 0
    t0 = time.time()
    for i in range(N):
        r = d.iloc[i]
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        if mode == "her" or (mode == "arada" and i % 6 == 0):
            qg = motion_blur(qg, severity, rng)
        dn = de = None
        if i > 0 and np.isfinite(dn_all[i - 1]):
            dn, de = float(dn_all[i - 1]), float(de_all[i - 1])
        res = seq.step(qg, qe[i], float(r.Kappa), float(r.Omega),
                       float(r.height), float(r.Phi1), dn, de)
        nl[i] = res.n_loftr
        if getattr(res, "skipped_blurry", False):
            skipped += 1
        if np.isfinite(res.north):
            err[i] = float(np.hypot(res.north - gt_n[i], res.east - gt_e[i]))
    sat.close()
    e = err[np.isfinite(err)]
    return {
        "medyan_m": float(np.median(e)), "p90_m": float(np.percentile(e, 90)),
        "max_m": float(e.max()), "ate_m": float(np.sqrt((e ** 2).mean())),
        "basari_10m": float((e <= 10).mean()), "basari_20m": float((e <= 20).mean()),
        "loftr": float(nl.mean()), "atlanan": int(skipped),
        "sure_dk": float((time.time() - t0) / 60),
    }


def show(tag, s):
    print("  {:>34}  medyan {:7.2f} m   p90 {:8.2f} m   <=20m %{:5.1f}   "
          "LoFTR {:.2f}   atlanan {:3d}".format(
              tag, s["medyan_m"], s["p90_m"], s["basari_20m"] * 100,
              s["loftr"], s["atlanan"]), flush=True)


def main():
    out = {}
    print("=== SENARYO 1: HER kare bulanik (siddet 0.6) ===")
    for gate, bm, tag in [(False, False, "duzeltmesiz (Faz 4 hali)"),
                          (True, False, "sadece keskinlik kapisi"),
                          (False, True, "sadece alan esitleme"),
                          (True, True, "ikisi birden")]:
        s = run(gate, bm, 0.6, "her")
        out[f"her_0.6_{int(gate)}{int(bm)}"] = s
        show(tag, s)

    print("\n=== SENARYO 2: ARADA BIR bulanik (her 6. kare, siddet 0.8) ===")
    for gate, bm, tag in [(False, False, "duzeltmesiz"),
                          (True, False, "sadece keskinlik kapisi"),
                          (True, True, "ikisi birden")]:
        s = run(gate, bm, 0.8, "arada")
        out[f"arada_0.8_{int(gate)}{int(bm)}"] = s
        show(tag, s)

    print("\n=== TEMIZ KARE (duzeltmeler zarar veriyor mu?) ===")
    for gate, bm, tag in [(False, False, "duzeltmesiz"),
                          (True, True, "ikisi birden")]:
        s = run(gate, bm, 0.0, "yok")
        out[f"temiz_{int(gate)}{int(bm)}"] = s
        show(tag, s)

    (ROOT / "results" / "13_blur_fix.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nresults/13_blur_fix.json yazildi")


if __name__ == "__main__":
    main()

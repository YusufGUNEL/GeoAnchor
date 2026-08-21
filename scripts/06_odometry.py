"""Faz 2 — görsel odometri: bağıl hareket ve sürüklenmenin ölçülmesi.

Amaç iki yönlü:
  1. Faz 3'ün parçacık süzgecine hareket modeli sağlamak.
  2. Sürüklenmeyi SAYIYLA göstermek — mutlak düzeltmenin neden şart olduğunun
     kanıtı. Sadece odometriyle uçan bir İHA 74 km sonra nereye düşer?
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
from src.geo import SatelliteMap, latlon_to_local_m
from src.geometry import AttitudeModel
from src.odometry import VisualOdometry, integrate

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
TILE_M, OUT_PX = 300.0, 640
M_PER_PX = TILE_M / OUT_PX          # 0.469 m/px
ATT = AttitudeModel(pitch_bias_deg=2.006, roll_bias_deg=-0.137)


def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    d = flight.df
    n = flight.n_frames

    vo = VisualOdometry(m_per_px=M_PER_PX)
    steps = []
    t0 = time.time()
    prev = cv2.cvtColor(np.ascontiguousarray(q[0]), cv2.COLOR_RGB2GRAY)
    for i in range(1, n):
        curr = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        steps.append(vo.step(prev, curr))
        prev = curr
        if i % 100 == 0:
            el = time.time() - t0
            print(f"  {i}/{n-1}  {el:.0f} sn, ~{el/i*(n-1-i):.0f} sn kaldi", flush=True)

    ok = np.array([s.ok for s in steps])
    inl = np.array([s.inliers for s in steps], dtype=float)
    rot = np.array([s.resid_rot_deg for s in steps])
    sc = np.array([s.resid_scale for s in steps])
    print(f"\nOdometri adimlari: {ok.sum()}/{len(ok)} tuttu (%{ok.mean()*100:.1f})")
    print(f"  medyan ic nokta   : {np.nanmedian(inl[ok]):.0f}")
    print(f"  artik donme       : ort {np.nanmean(rot[ok]):+.3f} deg, "
          f"std {np.nanstd(rot[ok]):.3f} deg")
    print(f"  artik olcek       : ort {np.nanmean(sc[ok]):.4f}, "
          f"std {np.nanstd(sc[ok]):.4f}")
    print(f"  sure              : {(time.time()-t0)/(n-1)*1000:.0f} ms/adim")

    # --- gorusel odometrinin olctugu, GORUNTU MERKEZININ yer hareketidir.
    # Duruş kaymasının degisimi cikarilarak IHA hareketine cevrilir.
    fwd, rgt = ATT.offset_body(d["Kappa"].values, d["Omega"].values,
                               d["height"].values)
    yaw = np.radians(d["Phi1"].values)
    off_n = fwd * np.cos(yaw) - rgt * np.sin(yaw)
    off_e = fwd * np.sin(yaw) + rgt * np.cos(yaw)
    d_off_n = np.diff(off_n)
    d_off_e = np.diff(off_e)

    raw_n = np.array([s.d_north_m if s.ok else np.nan for s in steps])
    raw_e = np.array([s.d_east_m if s.ok else np.nan for s in steps])
    cor_n = raw_n - d_off_n
    cor_e = raw_e - d_off_e

    gt_n = d["north_m"].values
    gt_e = d["east_m"].values
    true_dn = np.diff(gt_n)
    true_de = np.diff(gt_e)

    def step_stats(dn, de, name):
        m = np.isfinite(dn)
        en = dn[m] - true_dn[m]
        ee = de[m] - true_de[m]
        err = np.hypot(en, ee)
        print(f"  {name:>28}: adim hatasi medyan {np.median(err):.3f} m, "
              f"ort {err.mean():.3f} m, sapma (kuzey {en.mean():+.3f}, dogu {ee.mean():+.3f})")
        return err

    print("\nAdim basina dogruluk (gercek yer degistirmeye gore):")
    step_stats(raw_n, raw_e, "ham (goruntu merkezi)")
    step_stats(cor_n, cor_e, "durus duzeltmeli (IHA)")

    # --- yorunge kur ve suruklenmeyi olc ---
    def build(dn, de):
        north = np.zeros(n)
        east = np.zeros(n)
        north[0], east[0] = gt_n[0], gt_e[0]
        last = (0.0, 0.0)
        for i in range(n - 1):
            if np.isfinite(dn[i]):
                last = (dn[i], de[i])
            north[i + 1] = north[i] + last[0]
            east[i + 1] = east[i] + last[1]
        return north, east

    vo_n, vo_e = build(cor_n, cor_e)
    err = np.hypot(vo_n - gt_n, vo_e - gt_e)
    dist = d["cum_dist_m"].values

    print(f"\n=== FAZ 2: SADECE GORSEL ODOMETRI (surukleniyor) ===")
    print(f"  son hata          : {err[-1]:.1f} m  ({dist[-1]/1000:.1f} km sonra)")
    print(f"  mutlak yorunge hatasi (ATE, karekok ortalama): {np.sqrt((err**2).mean()):.1f} m")
    print(f"  medyan hata       : {np.median(err):.1f} m")
    print(f"  en buyuk hata     : {err.max():.1f} m")
    print(f"  suruklenme orani  : %{err[-1]/dist[-1]*100:.3f} (kat edilen yolun yuzdesi)")
    for km in [1, 5, 10, 25, 50, 74]:
        j = np.searchsorted(dist, km * 1000)
        if j < n:
            print(f"    {km:>2} km sonra    : {err[j]:7.1f} m")

    np.savez(ROOT / "results" / "06_odometry.npz",
             d_north=cor_n, d_east=cor_e, ok=ok, inliers=inl,
             vo_north=vo_n, vo_east=vo_e, err=err, dist=dist,
             raw_north=raw_n, raw_east=raw_e)
    summary = {
        "adim_tutma_orani": float(ok.mean()),
        "medyan_ic_nokta": float(np.nanmedian(inl[ok])),
        "son_hata_m": float(err[-1]),
        "ate_m": float(np.sqrt((err ** 2).mean())),
        "medyan_hata_m": float(np.median(err)),
        "max_hata_m": float(err.max()),
        "suruklenme_orani_yuzde": float(err[-1] / dist[-1] * 100),
        "toplam_km": float(dist[-1] / 1000),
    }
    (ROOT / "results" / "06_odometry.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print("\nresults/06_odometry.npz + .json yazildi")
    sat.close()


if __name__ == "__main__":
    main()

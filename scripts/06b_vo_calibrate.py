"""Faz 2b — odometri kalibrasyonu: pusula sapmasi + olcek.

Bulgu: odometrinin olctugu hareket yonu ile gercek yon arasindaki fark ucus
koluna gore degisiyor (kuzeybatiya giderken +1,65 derece, guneydoguya giderken
+7,22 derece). Bu rastgele degil: manyetometrenin sert-demir/yumusak-demir
hatasi tam olarak boyle davranir, yonelim hatasi yonun sinusoidal fonksiyonudur.
Havacilikta buna "pusula sapma egrisi" denir ve ucaklarda "compass swing"
islemiyle kalibre edilir.

Model:  d(yaw) = a*sin(yaw) + b*cos(yaw) + c
Kalibrasyon ucusun ilk %20'sinde yapilir (bu bolum her iki ucus kolunu da
icerdigi icin model belirlenebilir), degerlendirme kalan %80'de.

Ayrica tek bir olcek carpani kalibre edilir (irtifa/arazi kaynakli sabit hata).
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

from src.flight import load_flight

ROOT = Path(__file__).resolve().parents[1]
CAL_FRAC = 0.20


def wrap(x):
    return (x + 180) % 360 - 180


def main():
    z = np.load(ROOT / "results" / "06_odometry.npz")
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    d = flight.df
    dn, de = z["d_north"].copy(), z["d_east"].copy()
    tn = np.diff(d["north_m"].values)
    te = np.diff(d["east_m"].values)
    yaw = d["Phi1"].values[1:]
    ok = np.isfinite(dn) & (np.hypot(tn, te) > 50)

    idx = np.where(ok)[0]
    ncal = int(len(idx) * CAL_FRAC)
    cal, tst = idx[:ncal], idx[ncal:]
    print(f"Kalibrasyon {len(cal)} adim (ucusun ilk %{CAL_FRAC*100:.0f}'i), "
          f"degerlendirme {len(tst)} adim")
    print(f"  kalibrasyon bolumundeki yonelimler: "
          f"{np.unique(np.round(yaw[cal]/30)*30)}")

    # --- pusula sapma egrisi ---
    ang_vo = np.degrees(np.arctan2(de, dn))
    ang_gt = np.degrees(np.arctan2(te, tn))
    dth = wrap(ang_vo - ang_gt)

    yr = np.radians(yaw)
    A = np.stack([np.sin(yr[cal]), np.cos(yr[cal]), np.ones(len(cal))], 1)
    coef, *_ = np.linalg.lstsq(A, dth[cal], rcond=None)
    a, b, c = coef
    print(f"\nPusula sapma egrisi: d(yaw) = {a:+.3f}*sin(yaw) "
          f"{b:+.3f}*cos(yaw) {c:+.3f}   [derece]")
    print(f"  genlik {np.hypot(a,b):.2f} derece, sabit {c:+.2f} derece")

    def delta(y_deg):
        r = np.radians(y_deg)
        return a * np.sin(r) + b * np.cos(r) + c

    # --- duzeltmeyi uygula: her adimi -delta kadar dondur ---
    dl = np.radians(delta(yaw))
    cs, sn = np.cos(-dl), np.sin(-dl)
    rn = dn * cs - de * sn
    re = dn * sn + de * cs

    # --- olcek carpani (donme duzeltildikten SONRA) ---
    s = float(np.median(np.hypot(tn[cal], te[cal]) / np.hypot(rn[cal], re[cal])))
    rn, re = rn * s, re * s
    print(f"  olcek carpani: x{s:.4f}")

    def stats(x_n, x_e, sel, name):
        e = np.hypot(x_n[sel] - tn[sel], x_e[sel] - te[sel])
        print(f"  {name:>34}: medyan {np.median(e):6.3f} m   ort {e.mean():6.3f} m")
        return e

    print(f"\nADIM DOGRULUGU (degerlendirme kumesi, kalibrasyonda YOK):")
    stats(dn, de, tst, "duzeltmesiz")
    stats(rn, re, tst, "pusula + olcek duzeltmeli")

    # --- yorunge kur ---
    n = len(d)

    def build(a_n, a_e):
        north = np.zeros(n)
        east = np.zeros(n)
        north[0], east[0] = d["north_m"].values[0], d["east_m"].values[0]
        last = (0.0, 0.0)
        for i in range(n - 1):
            if np.isfinite(a_n[i]):
                last = (a_n[i], a_e[i])
            north[i + 1] = north[i] + last[0]
            east[i + 1] = east[i] + last[1]
        return north, east

    gt_n, gt_e = d["north_m"].values, d["east_m"].values
    dist = d["cum_dist_m"].values
    old_n, old_e = build(dn, de)
    new_n, new_e = build(rn, re)
    e_old = np.hypot(old_n - gt_n, old_e - gt_e)
    e_new = np.hypot(new_n - gt_n, new_e - gt_e)

    print(f"\nYORUNGE (sadece odometri, 73,9 km):")
    print(f"  {'duzeltmesiz':>26}: son hata {e_old[-1]:8.1f} m   "
          f"ATE {np.sqrt((e_old**2).mean()):8.1f} m   suruklenme %{e_old[-1]/dist[-1]*100:.3f}")
    print(f"  {'kalibrasyonlu':>26}: son hata {e_new[-1]:8.1f} m   "
          f"ATE {np.sqrt((e_new**2).mean()):8.1f} m   suruklenme %{e_new[-1]/dist[-1]*100:.3f}")

    np.savez(ROOT / "results" / "06b_odometry_cal.npz",
             d_north=rn, d_east=re, vo_north=new_n, vo_east=new_e,
             err=e_new, dist=dist, ok=ok,
             compass_a=a, compass_b=b, compass_c=c, scale=s)
    (ROOT / "results" / "06b_vo_calib.json").write_text(json.dumps({
        "compass_a_deg": float(a), "compass_b_deg": float(b),
        "compass_c_deg": float(c), "scale": float(s),
        "adim_medyan_duzeltmesiz_m": float(np.median(
            np.hypot(dn[tst] - tn[tst], de[tst] - te[tst]))),
        "adim_medyan_kalibrasyonlu_m": float(np.median(
            np.hypot(rn[tst] - tn[tst], re[tst] - te[tst]))),
        "son_hata_duzeltmesiz_m": float(e_old[-1]),
        "son_hata_kalibrasyonlu_m": float(e_new[-1]),
        "ate_duzeltmesiz_m": float(np.sqrt((e_old ** 2).mean())),
        "ate_kalibrasyonlu_m": float(np.sqrt((e_new ** 2).mean())),
    }, indent=2), encoding="utf-8")
    print("\nresults/06b_odometry_cal.npz + .json yazildi")


if __name__ == "__main__":
    main()

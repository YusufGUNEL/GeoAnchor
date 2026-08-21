"""Hata vektörü kamera eğimiyle açıklanıyor mu?

Gerçek konum temiz (±1,5 m). Öyleyse 17 m'lik hata bizim boru hattımızda.
En güçlü aday: İHA görüntüsü dik değil. 466 m irtifada 2°'lik eğim yerde
466*tan(2°) = 16 m kaydırır — ölçtüğümüz hatanın tam mertebesi.

Burada eğimin ürettiği kayma VEKTÖRÜNÜ modelleyip hata vektörüne regresyonla
oturtuyoruz. Skaler korelasyon zayıf çıkmıştı çünkü yön bilgisini atıyordu.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from src.flight import load_flight

ROOT = Path(__file__).resolve().parents[1]
z = np.load(ROOT / "results" / "04c_bias.npz")
dn, de, idx = z["dn"], z["de"], z["idx"]
flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sub = flight.df.iloc[idx]
h = sub["height"].values
om = np.radians(sub["Omega"].values)      # eğim
ka = np.radians(sub["Kappa"].values)      # yalpa
yaw = np.radians(sub["Phi1"].values)      # yönelim (kuzeyden saat yönünde)

print(f"n = {len(dn)}, hata: kuzey std {dn.std():.2f} m, doğu std {de.std():.2f} m")
print(f"eğim |Omega| ort {np.degrees(np.abs(om)).mean():.2f}°, "
      f"|Kappa| ort {np.degrees(np.abs(ka)).mean():.2f}°, irtifa ort {h.mean():.0f} m\n")

def fit(pn, pe, name):
    """Öngörülen kaymayı hataya en küçük karelerle oturt, açıklanan varyansı ver."""
    A = np.stack([np.concatenate([pn, pe]), np.ones(2*len(pn))], 1)
    y = np.concatenate([dn, de])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ coef
    r2 = 1 - resid.var() / y.var()
    rn = resid[:len(pn)]; re = resid[len(pn):]
    med = np.median(np.hypot(rn, re))
    print(f"  {name:>34}  katsayı {coef[0]:+6.3f}  R² {r2:+6.3f}  "
          f"kalan medyan hata {med:6.2f} m")
    return r2, med

print("Eğim kayma modelleri (ileri = h*tan(Omega), sağ = h*tan(Kappa), sonra yönelimle döndür):")
base = np.median(np.hypot(dn, de))
print(f"  {'(model yok)':>34}  {'':>14}  {'':>10}  kalan medyan hata {base:6.2f} m")
for s_om in (+1, -1):
    for s_ka in (+1, -1):
        for swap in (False, True):
            fwd = s_om * h * np.tan(om)
            rgt = s_ka * h * np.tan(ka)
            if swap: fwd, rgt = rgt, fwd
            # gövde çerçevesinden kuzey/doğuya
            pn = fwd * np.cos(yaw) - rgt * np.sin(yaw)
            pe = fwd * np.sin(yaw) + rgt * np.cos(yaw)
            fit(pn, pe, f"Omega{s_om:+d} Kappa{s_ka:+d}{' (yer değiştirmiş)' if swap else ''}")

# İki serbest katsayılı tam model: hata = a*(ileri yönü) + b*(sağ yönü)
print("\nİki serbest katsayılı model (ileri ve sağ ayrı ölçeklenir):")
f_n, f_e = np.cos(yaw), np.sin(yaw)          # ileri birim vektör (kuzey, doğu)
r_n, r_e = -np.sin(yaw), np.cos(yaw)         # sağ birim vektör
A = np.zeros((2*len(dn), 4))
A[:len(dn), 0] = h*np.tan(om)*f_n;  A[len(dn):, 0] = h*np.tan(om)*f_e
A[:len(dn), 1] = h*np.tan(ka)*r_n;  A[len(dn):, 1] = h*np.tan(ka)*r_e
A[:len(dn), 2] = 1.0
A[len(dn):, 3] = 1.0
y = np.concatenate([dn, de])
coef, *_ = np.linalg.lstsq(A, y, rcond=None)
resid = y - A @ coef
rn, re = resid[:len(dn)], resid[len(dn):]
print(f"  Omega katsayısı {coef[0]:+.3f}, Kappa katsayısı {coef[1]:+.3f}, "
      f"sabit kuzey {coef[2]:+.2f} m, doğu {coef[3]:+.2f} m")
print(f"  R² {1 - resid.var()/y.var():+.3f}")
print(f"  medyan hata {base:.2f} m -> {np.median(np.hypot(rn, re)):.2f} m")

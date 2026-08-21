"""Gerçek konum verisi ne kadar temiz? İHA düz hatlar uçuyor — sapma ölçülebilir.

Mantık: tarama deseninde İHA uzun düz hatlar boyunca sabit hızla uçar. O hatta
bir doğru uydurulursa, gerçek konumların doğrudan sapması GPS gürültüsünün
alt sınırını verir. Eğer bu sapma ~10 m ise, "gerçek konum" aslında ±10 m
belirsiz demektir ve ölçtüğümüz 17 m'lik hatanın önemli kısmı ölçme aracına ait.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from src.flight import load_flight

flight = load_flight(r"D:\GeoAnchorData\raw", "03")
d = flight.df
n = d["north_m"].values; e = d["east_m"].values
yaw = d["Phi1"].values

# --- düz hatları böl: yönelim 20°'den fazla değişince yeni hat ---
legs, start = [], 0
for i in range(1, len(d)):
    if abs(((yaw[i] - yaw[i-1] + 180) % 360) - 180) > 20:
        if i - start >= 15: legs.append((start, i))
        start = i
if len(d) - start >= 15: legs.append((start, len(d)))
print(f"{len(legs)} düz hat bulundu (>=15 kare)\n")

all_cross, all_dstep = [], []
print(f"{'hat':>4} {'kare':>6} {'uzunluk':>10} {'çapraz sapma':>14} {'adım std':>11}")
print("-" * 50)
for k, (a, b) in enumerate(legs):
    x, y = e[a:b], n[a:b]
    # doğrultuyu asıl bileşen analiziyle bul
    P = np.stack([x - x.mean(), y - y.mean()], 1)
    _, _, Vt = np.linalg.svd(P, full_matrices=False)
    along, cross = P @ Vt[0], P @ Vt[1]
    step = np.diff(np.sort(along))
    all_cross.append(cross); all_dstep.append(step - step.mean())
    print(f"{k:>4} {b-a:>6} {along.max()-along.min():>9.0f}m "
          f"{cross.std():>13.2f}m {step.std():>10.2f}m")

cross = np.concatenate(all_cross); dstep = np.concatenate(all_dstep)
print("-" * 50)
print(f"\nTüm hatlar birlikte ({len(cross)} kare):")
print(f"  çapraz sapma std      : {cross.std():.2f} m")
print(f"  çapraz sapma %95 aralık: ±{np.percentile(np.abs(cross),95):.2f} m")
print(f"  adım uzunluğu std      : {dstep.std():.2f} m")
print(f"\nYorum:")
print(f"  Bir İHA düz hatta uçarken gerçekten ±{cross.std():.0f} m yalpalamaz.")
print(f"  Bu sapma büyük ölçüde GPS gürültüsüdür.")
print(f"  Yani 'gerçek konum' verisinin kendi belirsizliği ~{cross.std():.0f} m mertebesinde.")

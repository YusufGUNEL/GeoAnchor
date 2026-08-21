"""17,75 m'lik tavan hatasının kaynağı ne? Üç hipotez birden sınanır.

H1: kamera eğimi (Omega/Kappa) merkezi yerden kaydırıyor  -> hata eğimle ilişkili olmalı
H2: benzerlik dönüşümü yetersiz, perspektif gerekiyor     -> homografi hatayı düşürmeli
H3: ölçek uyumsuzluğu (sorgu 0,469 vs uydu 0,625 m/px)    -> eşit ölçekte hata düşmeli
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m
from src.matching import LoFTRMatcher

CACHE = Path(r"D:\GeoAnchorData\cache")

def run(loc_sat, matcher, flight, q, idxs, crop_m, model):
    """model: 'sim' | 'homo' | 'affine'"""
    errs, angs, used = [], [], 0
    src_px = int(round(crop_m / loc_sat.gsd))
    for i in idxs:
        r = flight.df.iloc[i]
        img, x0, y0 = loc_sat.crop_around_latlon(float(r.lat), float(r.lon), src_px)
        crop = cv2.resize(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (640, 640),
                          interpolation=cv2.INTER_AREA)
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        pa, pb, _ = matcher.match(qg, crop)
        if len(pa) < 25:
            continue
        pa32, pb32 = pa.astype(np.float32), pb.astype(np.float32)
        if model == "sim":
            M, mask = cv2.estimateAffinePartial2D(pa32, pb32, method=cv2.RANSAC,
                                                  ransacReprojThreshold=4.0,
                                                  maxIters=10000, confidence=0.999)
            if M is None or mask.sum() < 25: continue
            u = M[0,0]*320 + M[0,1]*320 + M[0,2]; v = M[1,0]*320 + M[1,1]*320 + M[1,2]
            angs.append(np.degrees(np.arctan2(M[1,0], M[0,0])))
        elif model == "affine":
            M, mask = cv2.estimateAffine2D(pa32, pb32, method=cv2.RANSAC,
                                           ransacReprojThreshold=4.0,
                                           maxIters=10000, confidence=0.999)
            if M is None or mask.sum() < 25: continue
            u = M[0,0]*320 + M[0,1]*320 + M[0,2]; v = M[1,0]*320 + M[1,1]*320 + M[1,2]
            angs.append(np.degrees(np.arctan2(M[1,0], M[0,0])))
        else:
            H, mask = cv2.findHomography(pa32, pb32, cv2.USAC_MAGSAC, 4.0,
                                         maxIters=10000, confidence=0.999)
            if H is None or mask.sum() < 25: continue
            p = H @ np.array([320.0, 320.0, 1.0])
            u, v = p[0]/p[2], p[1]/p[2]
            angs.append(np.degrees(np.arctan2(H[1,0], H[0,0])))
        k = src_px / 640
        plat, plon = loc_sat.px_to_latlon(x0 + u*k, y0 + v*k)
        errs.append(haversine_m(float(r.lat), float(r.lon), float(plat), float(plon)))
        used += 1
    return np.array(errs), np.array(angs), used

def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    matcher = LoFTRMatcher(size=640)
    idxs = np.linspace(0, flight.n_frames - 1, 80).astype(int)

    print("=== H2/H3: dönüşüm modeli x kırpma boyutu ===")
    print(f"{'kırpma':>8} {'model':>8} {'n':>5} {'medyan':>9} {'ort':>9} {'%90':>9} {'<=5m':>7} {'<=10m':>7}")
    print("-" * 68)
    best = None
    for crop_m in [300, 400]:
        for model in ["sim", "affine", "homo"]:
            e, a, n = run(sat, matcher, flight, q, idxs, crop_m, model)
            if n == 0: continue
            print(f"{crop_m:>8} {model:>8} {n:>5} {np.median(e):>8.2f}m {e.mean():>8.2f}m "
                  f"{np.percentile(e,90):>8.2f}m {(e<=5).mean()*100:>6.1f}% {(e<=10).mean()*100:>6.1f}%")
            if best is None or np.median(e) < best[0]:
                best = (np.median(e), crop_m, model, e, idxs[:len(e)])

    # --- H1: eğim ilişkisi (en iyi ayarla) ---
    print(f"\n=== H1: hata kamera eğimiyle ilişkili mi? (en iyi ayar: {best[1]} m / {best[2]}) ===")
    e = best[3]
    # hatayla aynı sırada olan kareler
    sub = flight.df.iloc[idxs[:len(e)]]
    tilt = np.hypot(sub["Omega"].values, sub["Kappa"].values)
    pred_shift = 466.0 * np.tan(np.radians(tilt))
    for name, x in [("eğim büyüklüğü (°)", tilt),
                    ("eğimden beklenen kayma (m)", pred_shift),
                    ("|Omega| (°)", np.abs(sub["Omega"].values)),
                    ("|Kappa| (°)", np.abs(sub["Kappa"].values))]:
        c = np.corrcoef(x, e)[0, 1]
        print(f"  {name:>28} ile korelasyon: {c:+.3f}")
    print(f"  eğimden beklenen kayma: medyan {np.median(pred_shift):.1f} m, "
          f"ort {pred_shift.mean():.1f} m")
    print(f"  ölçülen hata          : medyan {np.median(e):.1f} m, ort {e.mean():.1f} m")
    sat.close()

if __name__ == "__main__":
    main()

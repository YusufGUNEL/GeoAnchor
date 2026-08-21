"""Tavan ölçümü: gerçek konum BİLİNİYORKEN eşleme ne kadar hassas?

Bu, Faz 1'in ulaşabileceği en iyi doğruluğu verir. Getirme mükemmel olsa bile
eşleme+geometri bu hatanın altına inemez.
"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np, cv2
from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m
from src.matching import LoFTRMatcher
from src.localize import SingleFrameLocalizer

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]

def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    g = np.load(CACHE / "tilegrid_03.npz")
    te = np.load(CACHE / "tile_emb_448.npy")
    matcher = LoFTRMatcher(size=640)
    loc = SingleFrameLocalizer(sat, g["lat"], g["lon"], te, matcher)

    idxs = np.linspace(0, flight.n_frames - 1, 120).astype(int)
    errs, inl, scales, angs, fails = [], [], [], [], 0
    t0 = time.time()
    for j, i in enumerate(idxs):
        r = flight.df.iloc[i]
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        f = loc.match_at(qg, float(r.lat), float(r.lon))
        if not f.ok:
            fails += 1
            continue
        errs.append(haversine_m(float(r.lat), float(r.lon), f.lat, f.lon))
        inl.append(f.inliers); scales.append(f.scale); angs.append(f.angle)
        if (j + 1) % 30 == 0:
            print(f"  {j+1}/{len(idxs)}  medyan hata {np.median(errs):.2f} m")

    e = np.array(errs)
    print(f"\n=== TAVAN (gerçek konum biliniyorken eşleme) — {len(idxs)} kare ===")
    print(f"  eşleme tutmayan     : {fails} ({fails/len(idxs)*100:.1f}%)")
    print(f"  medyan hata         : {np.median(e):.2f} m")
    print(f"  ortalama hata       : {e.mean():.2f} m")
    print(f"  %90 dilim           : {np.percentile(e,90):.2f} m")
    for t in [1,3,5,10,20]:
        print(f"  {t:>2} m içinde        : {(e<=t).mean()*100:5.1f}%")
    print(f"  medyan iç nokta     : {np.median(inl):.0f}")
    print(f"  ölçek  ort/std      : {np.mean(scales):.3f} / {np.std(scales):.3f}")
    print(f"  artık açı ort/std   : {np.mean(angs):.2f}° / {np.std(angs):.2f}°")
    print(f"  süre                : {(time.time()-t0)/len(idxs)*1000:.0f} ms/kare")
    np.save(ROOT / "results" / "04_oracle_errs.npy", e)
    sat.close()

if __name__ == "__main__":
    main()

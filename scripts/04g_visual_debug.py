"""Hatayı gözle gör: İHA kırpmasını uydu kırpmasına bindirip nereye düştüğüne bak."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m
from src.matching import LoFTRMatcher

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
CROP_M, OUT = 400.0, 640

flight = load_flight(r"D:\GeoAnchorData\raw", "03")
sat = SatelliteMap(flight.satellite_path)
q = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
matcher = LoFTRMatcher(size=640)

idxs = [60, 250, 430, 690]
fig, axes = plt.subplots(len(idxs), 3, figsize=(15, 5 * len(idxs)))
for row, i in enumerate(idxs):
    r = flight.df.iloc[i]
    crop_rgb, x0, y0, mpp = sat.crop_meters(float(r.lat), float(r.lon), CROP_M, OUT)
    crop_g = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
    qrgb = np.ascontiguousarray(q[i]); qg = cv2.cvtColor(qrgb, cv2.COLOR_RGB2GRAY)

    pa, pb, _ = matcher.match(qg, crop_g)
    H, mask = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32),
                                 cv2.USAC_MAGSAC, 4.0, maxIters=10000, confidence=0.999)
    p = H @ np.array([320., 320., 1.]); u, v = p[0]/p[2], p[1]/p[2]
    mx, my = sat.out_px_to_map_px(u, v, x0, y0, CROP_M, OUT)
    plat, plon = sat.px_to_latlon(mx, my)
    err = haversine_m(float(r.lat), float(r.lon), float(plat), float(plon))

    warped = cv2.warpPerspective(qrgb, H, (OUT, OUT))
    m = (warped.sum(2) > 0)
    blend = crop_rgb.copy()
    blend[m] = (0.5 * crop_rgb[m] + 0.5 * warped[m]).astype(np.uint8)

    axes[row,0].imshow(qrgb); axes[row,0].set_title(f"İHA kuzey-yukarı {r.filename}", fontsize=9)
    axes[row,0].plot(320,320,'o',color='#00ff6a',ms=9)
    axes[row,1].imshow(crop_rgb)
    axes[row,1].set_title(f"Uydu {CROP_M:.0f} m kırpma ({mpp:.3f} m/px)", fontsize=9)
    axes[row,1].plot(320,320,'o',color='#00ff6a',ms=9,label='gerçek konum')
    axes[row,1].plot(u,v,'x',color='#ff2d55',ms=12,mew=3,label=f'kestirim ({err:.1f} m)')
    axes[row,1].legend(fontsize=8, loc='upper right')
    axes[row,2].imshow(blend)
    axes[row,2].set_title(f"Bindirme (İHA homografiyle oturtuldu) — "
                          f"{int(mask.sum())} iç nokta", fontsize=9)
    axes[row,2].plot(320,320,'o',color='#00ff6a',ms=9)
    axes[row,2].plot(u,v,'x',color='#ff2d55',ms=12,mew=3)
    for ax in axes[row]: ax.axis('off')
    print(f"kare {i}: hata {err:6.2f} m, iç nokta {int(mask.sum()):4d}, "
          f"kayma (u,v) = ({u-320:+.1f}, {v-320:+.1f}) px = "
          f"({(u-320)*mpp:+.1f}, {(v-320)*mpp:+.1f}) m")

fig.suptitle("Neden 17 m hata var? — yeşil daire gerçek konum, kırmızı çarpı kestirim", fontsize=13)
fig.tight_layout()
fig.savefig(ROOT / "figures" / "04_hata_teshis.png", dpi=95, bbox_inches="tight")
print("\nfigures/04_hata_teshis.png yazıldı")
sat.close()

"""[TARIHSEL — KULLANMA, yerine 03c_retrieval_sweep.py]

Bu betik IHA karesini gri tonlamaya cevirip uydunun RENKLI karolariyla
kiyasliyordu; bu yapay alan farki getirmeyi cokertiyordu (R@1 %7,3).
Hata bulunup duzeltildi. Depoda duruyor cunku ILERLEME.md o olcume atif
yapiyor ve sonucun nasil duzeldigi ancak ikisi yan yana gorulunce anlasilir.

Faz 1b — küresel getirme ne kadar iyi? Üç tanımlayıcı türü kıyaslanır.

Karo gömmesi cls ve GeM parçalarının birleşimi olarak saklandı; buradan
üçünü de (yalnız cls, yalnız GeM, birleşik) yeniden veritabanı kurmadan
değerlendirebiliyoruz.
"""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2, numpy as np
from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m_array
from src.features import Dinov2Embedder
from src.preprocess import drone_to_northup
from src.tiles import TileDB

DATA_ROOT = r"D:\GeoAnchorData\raw"
DRONE_GSD, TILE_M = 0.1142, 300.0
ROOT = Path(__file__).resolve().parents[1]
KS = [1, 3, 5, 10, 20, 50]
THRESH = [75, 150, 300]

def slice_norm(e, part):
    d = e.shape[1] // 2
    v = e[:, :d] if part == "cls" else (e[:, d:] if part == "gem" else e)
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def main():
    flight = load_flight(DATA_ROOT, "03")
    sat = SatelliteMap(flight.satellite_path)
    db = TileDB.load(ROOT / "data" / "tiledb_03.npz")
    emb_model = Dinov2Embedder(img_size=224, mode="both")

    # --- sorgu gömmeleri (İHA kareleri, kuzey yukarı) ---
    print(f"{flight.n_frames} kare gömülüyor...")
    t0 = time.time()
    qs, BATCH = [], 32
    buf = []
    for i in range(flight.n_frames):
        im = cv2.imread(str(flight.image_path(i)))
        nu = drone_to_northup(im, float(flight.df["Phi1"].iloc[i]),
                              DRONE_GSD, sat.gsd, TILE_M, yaw_sign=-1.0)
        buf.append(cv2.cvtColor(nu, cv2.COLOR_GRAY2RGB))
        if len(buf) == BATCH or i == flight.n_frames - 1:
            qs.append(emb_model.embed(np.stack(buf), batch=BATCH))
            buf = []
    q_emb = np.concatenate(qs, 0)
    print(f"  {time.time()-t0:.0f} sn ({flight.n_frames/(time.time()-t0):.1f} kare/sn)")
    np.save(ROOT / "data" / "query_emb_03.npy", q_emb)

    gt_lat = flight.df["lat"].values
    gt_lon = flight.df["lon"].values
    results = {}

    print(f"\n{'tanımlayıcı':>12} {'K':>4} " +
          " ".join(f"R@{t}m".rjust(8) for t in THRESH) + f" {'medyan en iyi':>14}")
    print("-" * 62)

    for part in ["cls", "gem", "both"]:
        dbe = slice_norm(db.emb, part)
        qe = slice_norm(q_emb, part)
        sims = qe @ dbe.T                                  # (768, 2709)
        order = np.argsort(-sims, axis=1)
        # her sorgu icin her karonun gercek konuma uzakligi
        results[part] = {}
        for k in KS:
            top = order[:, :k]
            d = haversine_m_array(gt_lat[:, None], gt_lon[:, None],
                                  db.lat[top], db.lon[top])     # (768, k)
            best = d.min(axis=1)
            row = [float((best <= t).mean()) for t in THRESH]
            results[part][k] = {"recall": row, "median_best_m": float(np.median(best))}
            print(f"{part:>12} {k:>4} " +
                  " ".join(f"{v*100:7.1f}%" for v in row) +
                  f" {np.median(best):13.1f} m")
        print()

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "03_getirme.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    print("results/03_getirme.json yazıldı.")
    sat.close()

if __name__ == "__main__":
    main()

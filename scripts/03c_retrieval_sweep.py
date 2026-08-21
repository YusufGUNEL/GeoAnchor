"""Faz 1b — küresel getirme taraması: renk düzeltmesi + girdi çözünürlüğü + havuzlama."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from src.flight import load_flight
from src.geo import haversine_m_array
from src.features import Dinov2Embedder

CACHE = Path(r"D:\GeoAnchorData\cache")
ROOT = Path(__file__).resolve().parents[1]
KS = [1, 3, 5, 10, 20, 50]
THRESH = [75, 150, 300]

def embed_all(model, arr, batch=24, tag=""):
    out = []
    t0 = time.time()
    for i in range(0, len(arr), batch):
        out.append(model.embed(np.ascontiguousarray(arr[i:i + batch]), batch=batch))
    v = np.concatenate(out, 0)
    print(f"      {tag}: {len(arr)} görüntü, {time.time()-t0:.0f} sn")
    return v

def slice_norm(e, part):
    d = e.shape[1] // 2
    v = e[:, :d] if part == "cls" else (e[:, d:] if part == "gem" else e)
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def main():
    flight = load_flight(r"D:\GeoAnchorData\raw", "03")
    g = np.load(CACHE / "tilegrid_03.npz")
    tiles = np.load(CACHE / "tiles_03_448.npy", mmap_mode="r")
    queries = np.load(CACHE / "northup_03_640.npy", mmap_mode="r")
    gt_lat, gt_lon = flight.df["lat"].values, flight.df["lon"].values
    print(f"{len(tiles)} karo, {len(queries)} sorgu\n")

    all_res = {}
    print(f"{'girdi':>6} {'havuz':>6} {'K':>4} " +
          " ".join(f"R@{t}m".rjust(8) for t in THRESH) + f" {'medyan':>10}")
    print("-" * 56)

    for size in [224, 336, 448]:
        model = Dinov2Embedder(img_size=size, mode="both")
        te = embed_all(model, tiles, tag=f"karo@{size}")
        qe = embed_all(model, queries, tag=f"sorgu@{size}")
        for part in ["cls", "gem", "both"]:
            dbe, q = slice_norm(te, part), slice_norm(qe, part)
            order = np.argsort(-(q @ dbe.T), axis=1)
            for k in KS:
                top = order[:, :k]
                d = haversine_m_array(gt_lat[:, None], gt_lon[:, None],
                                      g["lat"][top], g["lon"][top])
                best = d.min(axis=1)
                row = [float((best <= t).mean()) for t in THRESH]
                all_res[f"{size}_{part}_{k}"] = {
                    "recall": row, "median_best_m": float(np.median(best))}
                if k in (1, 5, 20):
                    print(f"{size:>6} {part:>6} {k:>4} " +
                          " ".join(f"{v*100:7.1f}%" for v in row) +
                          f" {np.median(best):9.0f} m")
        print()
        del model
        import torch; torch.cuda.empty_cache()
        # en iyi ayarı sonra kullanmak üzere sakla
        np.save(CACHE / f"tile_emb_{size}.npy", te)
        np.save(CACHE / f"query_emb_{size}.npy", qe)

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "03_getirme_tarama.json").write_text(
        json.dumps(all_res, indent=2), encoding="utf-8")
    print("results/03_getirme_tarama.json yazıldı.")

if __name__ == "__main__":
    main()

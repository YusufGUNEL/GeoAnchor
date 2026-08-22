"""Esleyici kiyaslamasi: LoFTR vs RoMa.

Cok ucuslu degerlendirme sunu gosterdi: basarimi belirleyen sey esleme
kalitesi. Ucus 08'de gercek konumda BILE medyan 8 ic nokta cikiyor, ucus 03'te
544. Yani darboğaz suzgec veya fuzyon degil, ESLEYICI.

Bu betik iki esleyiciyi ayni karelerde, gercek konumda karsilastirir. Konum
aramasi devrede degil — dogru yere bakiliyor. Fark varsa dogrudan esleyiciden
gelir.

Olculenler: ic nokta sayisi, esleme tutma orani, konum hatasi, sure, VRAM.
"""
import sys
import json
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import torch

from src.flight import load_flight
from src.geo import SatelliteMap, haversine_m
from src.matching import LoFTRMatcher

DATA = r"D:\GeoAnchorData\full"
CACHE = Path(r"D:\GeoAnchorData\cache_multi")
ROOT = Path(__file__).resolve().parents[1]
CROP_M, OUT_PX = 400.0, 640


class RomaMatcher:
    """RoMa sarmalayici — LoFTRMatcher ile ayni arayuz.

    RoMa yogun bir eslesme alani uretir; guven esigine gore orneklem alinir.
    4 GB'lik kartta calisabilmek icin kaba/ince cozunurluk dusuk tutuluyor.
    """

    def __init__(self, coarse=280, upsample=448, n_sample=5000, device="cuda"):
        from romatch import roma_outdoor
        self.model = roma_outdoor(device=device, coarse_res=coarse,
                                  upsample_res=upsample)
        self.model.upsample_preds = False
        self.n_sample = n_sample
        self.device = device
        self.size = upsample

    @torch.no_grad()
    def match(self, img_a: np.ndarray, img_b: np.ndarray):
        from PIL import Image
        ha, wa = img_a.shape[:2]
        hb, wb = img_b.shape[:2]
        pa_img = Image.fromarray(cv2.cvtColor(img_a, cv2.COLOR_GRAY2RGB)
                                 if img_a.ndim == 2 else img_a)
        pb_img = Image.fromarray(cv2.cvtColor(img_b, cv2.COLOR_GRAY2RGB)
                                 if img_b.ndim == 2 else img_b)
        warp, cert = self.model.match(pa_img, pb_img, device=self.device)
        matches, c = self.model.sample(warp, cert, num=self.n_sample)
        kpa, kpb = self.model.to_pixel_coordinates(matches, ha, wa, hb, wb)
        return (kpa.cpu().numpy(), kpb.cpu().numpy(),
                c.cpu().numpy() if hasattr(c, "cpu") else np.asarray(c))


def evaluate(fid: str, matcher, name: str, n: int = 24) -> dict:
    flight = load_flight(DATA, fid)
    sat = SatelliteMap(flight.satellite_path)
    q = np.load(CACHE / f"northup_{fid}_640.npy", mmap_mode="r")
    idxs = np.linspace(0, flight.n_frames - 1, n).astype(int)
    inl, errs, t_all = [], [], []
    torch.cuda.reset_peak_memory_stats()
    for i in idxs:
        r = flight.df.iloc[i]
        if not sat.contains(float(r.lat), float(r.lon)):
            continue
        crop_rgb, x0, y0, _ = sat.crop_meters(float(r.lat), float(r.lon),
                                              CROP_M, OUT_PX)
        qi = np.ascontiguousarray(q[i])
        t0 = time.time()
        if name == "LoFTR":
            pa, pb, _ = matcher.match(cv2.cvtColor(qi, cv2.COLOR_RGB2GRAY),
                                      cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY))
        else:
            pa, pb, _ = matcher.match(qi, crop_rgb)
        t_all.append(time.time() - t0)
        if len(pa) < 30:
            inl.append(0)
            continue
        H, mask = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32),
                                     cv2.USAC_MAGSAC, 4.0, maxIters=10_000,
                                     confidence=0.999)
        if H is None or mask is None:
            inl.append(0)
            continue
        k = int(mask.sum())
        inl.append(k)
        if k >= 40:
            p = H @ np.array([OUT_PX / 2, OUT_PX / 2, 1.0])
            if abs(p[2]) > 1e-9:
                u, v = p[0] / p[2], p[1] / p[2]
                mx, my = sat.out_px_to_map_px(u, v, x0, y0, CROP_M, OUT_PX)
                la, lo = sat.px_to_latlon(mx, my)
                errs.append(haversine_m(float(r.lat), float(r.lon),
                                        float(la), float(lo)))
    sat.close()
    inl = np.array(inl)
    return {"esleyici": name, "ucus": fid,
            "medyan_ic_nokta": float(np.median(inl)),
            "ort_ic_nokta": float(inl.mean()),
            "tutma_orani": float((inl >= 40).mean()),
            "medyan_hata_m": float(np.median(errs)) if errs else float("nan"),
            "n_konum": len(errs),
            "ms": float(np.mean(t_all) * 1000),
            "vram_mb": float(torch.cuda.max_memory_allocated() / 1e6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flights", default="03 01 05 02 08 10")
    a = ap.parse_args()
    fl = a.flights.split()

    out = []
    print("=== LoFTR (mevcut) ===")
    m = LoFTRMatcher(size=640)
    for fid in fl:
        r = evaluate(fid, m, "LoFTR")
        out.append(r)
        print("  ucus %s: medyan ic nokta %5.0f | tutma %%%3.0f | hata %7.2f m "
              "| %4.0f ms | VRAM %4.0f MB" % (
                  fid, r["medyan_ic_nokta"], r["tutma_orani"] * 100,
                  r["medyan_hata_m"], r["ms"], r["vram_mb"]), flush=True)
    del m
    torch.cuda.empty_cache()

    print("\n=== RoMa ===")
    try:
        m = RomaMatcher()
    except Exception as ex:
        print("  RoMa yuklenemedi:", str(ex)[:200])
        return
    for fid in fl:
        try:
            r = evaluate(fid, m, "RoMa")
            out.append(r)
            print("  ucus %s: medyan ic nokta %5.0f | tutma %%%3.0f | hata %7.2f m "
                  "| %4.0f ms | VRAM %4.0f MB" % (
                      fid, r["medyan_ic_nokta"], r["tutma_orani"] * 100,
                      r["medyan_hata_m"], r["ms"], r["vram_mb"]), flush=True)
        except Exception as ex:
            print("  ucus %s BASARISIZ: %s" % (fid, str(ex)[:160]), flush=True)
            torch.cuda.empty_cache()

    (ROOT / "results" / "25_matcher_bakeoff.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== KARSILASTIRMA ===")
    print("%-6s %22s %22s" % ("ucus", "LoFTR (ic nokta/tutma)", "RoMa (ic nokta/tutma)"))
    for fid in fl:
        L = next((x for x in out if x["ucus"] == fid and x["esleyici"] == "LoFTR"), None)
        R = next((x for x in out if x["ucus"] == fid and x["esleyici"] == "RoMa"), None)
        if L and R:
            print("%-6s %13.0f / %%%3.0f %13.0f / %%%3.0f" % (
                fid, L["medyan_ic_nokta"], L["tutma_orani"] * 100,
                R["medyan_ic_nokta"], R["tutma_orani"] * 100))


if __name__ == "__main__":
    main()

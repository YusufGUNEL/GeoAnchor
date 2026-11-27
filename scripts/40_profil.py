"""Uçtan uca süre: ham JPEG'den konuma, önbelleksiz, adım adım (yol haritası 1.1).

07_sequential kare başına ~0,8 sn diyor ama kuzey-yukarı kırpma, DINOv2 gömmesi
ve odometri önceden hesaplanıp diskten okunuyor. Burada her kare canlı bir
sistemdeki gibi işlenir:

  oku      : 3976x2652 JPEG -> bellek
  kuzey    : yöne göre çevir, uydu ölçeğine indir, 640 px kırp
  odometri : SIFT, önceki kareye göre
  gömme    : DINOv2 (yalnızca küresel aramada kullanılıyor; her karede de ölçülür)
  füzyon   : LoFTR eşleme + parçacık süzgeci (SequentialLocalizer.step)

Konum hatası da hesaplanır: önbelleksiz yol 07 ile aynı sonucu vermeli.

    python scripts/40_profil.py                 # uçuş 03, 768 kare
    python scripts/40_profil.py --max-frames 150
Çıktı: results/40_profil.json. Güç modu Dengeli/Performans olmalı (bkz. ILERLEME Faz 17).
"""
import sys
import time
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from src import paths  # noqa: E402
from src.flight import load_flight  # noqa: E402
from src.geo import SatelliteMap  # noqa: E402
from src.geometry import AttitudeModel  # noqa: E402
from src.matching import LoFTRMatcher  # noqa: E402
from src.localize import SingleFrameLocalizer  # noqa: E402
from src.particle_filter import PFConfig  # noqa: E402
from src.sequential import SequentialLocalizer  # noqa: E402
from src.preprocess import drone_to_northup  # noqa: E402
from src.odometry import VisualOdometry  # noqa: E402
from src.features import Dinov2Embedder  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = paths.CACHE
ATT = AttitudeModel(pitch_bias_deg=2.006, roll_bias_deg=-0.137)  # 07 ile aynı
DRONE_GSD, TILE_M, OUT_PX = 0.1142, 300.0, 640                     # 03a ile aynı
STAGES = ["oku", "kuzey", "odometri", "gomme", "fuzyon"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-frames", type=int, default=None)
    a = ap.parse_args()

    flight = load_flight(str(paths.RAW), "03")
    sat = SatelliteMap(flight.satellite_path)
    g = np.load(CACHE / "tilegrid_03.npz")
    te = np.load(CACHE / "tile_emb_448.npy")      # harita tarafı: uçuştan önce hazırlanır
    loc = SingleFrameLocalizer(sat, g["lat"], g["lon"], te, LoFTRMatcher(size=640), ATT)
    d = flight.df
    seq = SequentialLocalizer(sat, loc, ATT, float(d["lat"].iloc[0]), float(d["lon"].iloc[0]),
                              pf_cfg=PFConfig(n_particles=600), use_online_yaw=True, seed=0)
    vo = VisualOdometry(m_per_px=TILE_M / OUT_PX)
    emb = Dinov2Embedder(img_size=448, mode="both")

    # Gömmenin bu karede gerçekten kullanılıp kullanılmadığını işaretle
    used = {"emb": False}
    orig = loc.localize

    def flagged(*args, **kw):
        used["emb"] = True
        return orig(*args, **kw)
    loc.localize = flagged

    n = flight.n_frames if a.max_frames is None else min(a.max_frames, flight.n_frames)
    T = {s: np.zeros(n) for s in STAGES}
    emb_used = np.zeros(n, bool)
    err = np.full(n, np.nan)
    gt_n, gt_e = d["north_m"].values, d["east_m"].values

    # ısınma: CUDA çekirdekleri ilk çağrıda derleniyor, ölçüme girmesin
    _ = emb.embed(np.zeros((1, OUT_PX, OUT_PX, 3), np.uint8), batch=1)
    torch.cuda.synchronize()

    prev = None
    t_all = time.time()
    for i in range(n):
        r = d.iloc[i]
        t0 = time.perf_counter()
        im = cv2.imread(str(flight.image_path(i)))
        t1 = time.perf_counter()
        nu = drone_to_northup(im, float(r.Phi1), DRONE_GSD, sat.gsd, TILE_M,
                              yaw_sign=-1.0, out_px=OUT_PX)
        gray = cv2.cvtColor(nu, cv2.COLOR_BGR2GRAY)
        t2 = time.perf_counter()
        # 06 ile aynı: SIFT görüntü merkezinin hareketini ölçer; duruştan
        # (pitch/roll/irtifa) gelen merkez kaymasının değişimi çıkarılır.
        fwd, rgt = ATT.offset_body(np.array([r.Kappa]), np.array([r.Omega]),
                                   np.array([r.height]))
        yaw = np.radians(float(r.Phi1))
        off = (float(fwd[0] * np.cos(yaw) - rgt[0] * np.sin(yaw)),
               float(fwd[0] * np.sin(yaw) + rgt[0] * np.cos(yaw)))
        dn = de = None
        if prev is not None:
            s = vo.step(prev, gray)
            if s.ok:
                dn = s.d_north_m - (off[0] - prev_off[0])
                de = s.d_east_m - (off[1] - prev_off[1])
        prev, prev_off = gray, off
        t3 = time.perf_counter()
        qe = emb.embed(cv2.cvtColor(nu, cv2.COLOR_BGR2RGB)[None], batch=1)[0]
        t4 = time.perf_counter()
        used["emb"] = False
        res = seq.step(gray, qe, float(r.Kappa), float(r.Omega), float(r.height),
                       float(r.Phi1), dn, de)
        t5 = time.perf_counter()

        for s_, dt in zip(STAGES, (t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4)):
            T[s_][i] = dt * 1000
        emb_used[i] = used["emb"]
        if np.isfinite(res.north):
            err[i] = float(np.hypot(res.north - gt_n[i], res.east - gt_e[i]))
        if (i + 1) % 50 == 0:
            el = time.time() - t_all
            print(f"  {i+1}/{n}  medyan hata {np.nanmedian(err[:i+1]):.1f} m  "
                  f"~{el/(i+1)*(n-i-1)/60:.1f} dk kaldı", flush=True)

    total_always = sum(T[s] for s in STAGES)                 # gömme her karede
    total_lazy = total_always - np.where(emb_used, 0, T["gomme"])  # yalnızca gerektiğinde

    def st(x):
        return {"medyan": float(np.median(x)), "ort": float(x.mean()),
                "p95": float(np.percentile(x, 95)), "max": float(x.max())}

    e = err[np.isfinite(err)]
    out = {
        "ucus": "03", "n": int(n), "gpu": torch.cuda.get_device_name(0),
        "asama_ms": {s: st(T[s]) for s in STAGES},
        "toplam_ms_gomme_her_karede": st(total_always),
        "toplam_ms_gomme_gerektiginde": st(total_lazy),
        "gomme_kullanilan_kare": int(emb_used.sum()),
        "kapsama": float(len(e) / n), "medyan_hata_m": float(np.median(e)),
        "p90_hata_m": float(np.percentile(e, 90)),
    }
    print(f"\n=== UÇTAN UCA SÜRE (uçuş 03, {n} kare, önbelleksiz) ===")
    print(f"  {'aşama':10s} {'medyan':>8s} {'ort':>8s} {'p95':>8s}  ms")
    for s_ in STAGES:
        v = out["asama_ms"][s_]
        print(f"  {s_:10s} {v['medyan']:8.0f} {v['ort']:8.0f} {v['p95']:8.0f}")
    for k, lab in (("toplam_ms_gomme_gerektiginde", "TOPLAM"),
                   ("toplam_ms_gomme_her_karede", "(gömme her karede)")):
        v = out[k]
        print(f"  {lab:10s} {v['medyan']:8.0f} {v['ort']:8.0f} {v['p95']:8.0f}")
    print(f"  gömme kullanılan kare: {out['gomme_kullanilan_kare']}/{n}")
    print(f"  kapsama %{out['kapsama']*100:.1f}, medyan hata {out['medyan_hata_m']:.2f} m, "
          f"%90 {out['p90_hata_m']:.2f} m")

    p = ROOT / "results" / "40_profil.json"
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{p.name} yazıldı")
    sat.close()


if __name__ == "__main__":
    main()

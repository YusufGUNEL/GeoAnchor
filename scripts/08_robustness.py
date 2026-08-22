"""Faz 4 — reddedilme ve bozulma testleri.

Iki ayri soru:
  A. Olcum kesilirse ne olur? (GPS'in yerini alan uydu eslemesi de her karede
     tutmayabilir; dusman ortaminda kamera kapali kalabilir.)
  B. Goruntu bozulursa ne olur? (sis, gece, titresim, sikistirma, kapanma)

Her kosul icin sirali fuzyon bastan calistirilir ve hata dagilimi olculur.
Kisa surmesi icin ucusun ilk bolumu kullanilir (varsayilan 300 kare = ~29 km).
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from src.degrade import make_degrader

import importlib.util
spec = importlib.util.spec_from_file_location("seq07", ROOT / "scripts" / "07_sequential.py")
seq07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seq07)

N_FRAMES = 300


OUT = ROOT / "results" / "08_robustness.json"


def line(tag, s):
    if s.get("kapsama", 1.0) == 0.0:
        return f"  {tag:>26}  SISTEM HIC BASLAYAMADI (kapsama %0)"
    return (f"  {tag:>26}  medyan {s['medyan_m']:7.2f} m   "
            f"%90 {s['p90_m']:7.2f} m   en buyuk {s['max_m']:8.1f} m   "
            f"<=10m %{s['basari_10m']*100:5.1f}   LoFTR/kare {s['loftr_per_frame']:.2f}")


def load_done():
    """Onceki calistirmadan kalan sonuclari yukle (kaldigi yerden devam)."""
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"olcum_kesintisi": {}, "bozulma": {}}


def save(results):
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                   encoding="utf-8")


def main():
    results = load_done()
    t0 = time.time()

    print("=== A. OLCUM KESINTISI (uydu eslemesi zorla atiliyor) ===")
    print(f"  {'atilan olcum orani':>26}  {'sonuc':>0}")
    for drop in [0.0, 0.25, 0.50, 0.75, 0.90]:
        key = f"{int(drop*100)}%"
        if key in results["olcum_kesintisi"]:
            print(line(f"%{int(drop*100)} atildi (onceden)",
                       results["olcum_kesintisi"][key]))
            continue
        s, _, _ = seq07.run(drop_rate=drop, tag=f"drop{int(drop*100)}",
                            verbose=False, max_frames=N_FRAMES)
        results["olcum_kesintisi"][key] = s
        save(results)
        print(line(f"%{int(drop*100)} atildi", s))
        print(f"    -> gecen sure {(time.time()-t0)/60:.1f} dk", flush=True)

    print("\n=== B. GORUNTU BOZULMASI ===")
    conds = [
        ("hareket bulanikligi", [0.3, 0.6, 1.0]),
        ("sis", [0.3, 0.6, 1.0]),
        ("dusuk isik", [0.3, 0.6, 1.0]),
        ("jpeg sikistirma", [0.5, 1.0]),
        ("kapanma", [0.3, 0.6]),
        ("cozunurluk kaybi", [0.5, 1.0]),
    ]
    for name, sevs in conds:
        for sev in sevs:
            tag = f"{name.replace(' ', '_')}_{int(sev*100)}"
            if tag in results["bozulma"]:
                print(line(f"{name} {sev:.1f} (onceden)", results["bozulma"][tag]))
                continue
            s, _, _ = seq07.run(drop_rate=0.0, tag=tag, verbose=False,
                                max_frames=N_FRAMES,
                                degrade=make_degrader(name, sev))
            results["bozulma"][tag] = s
            save(results)
            print(line(f"{name} {sev:.1f}", s), flush=True)

    save(results)
    print(f"\nToplam sure: {(time.time()-t0)/60:.1f} dk")
    print("results/08_robustness.json yazildi")


if __name__ == "__main__":
    main()

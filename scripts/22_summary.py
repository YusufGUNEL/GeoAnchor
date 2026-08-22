"""Cok ucuslu sonuclari tek tabloda toplar ve README icin metin uretir."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def main():
    mf = json.loads((RES / "20_multiflight.json").read_text(encoding="utf-8"))
    diff = {}
    p = RES / "21_flight_difficulty.json"
    if p.exists():
        diff = json.loads(p.read_text(encoding="utf-8"))

    rows = []
    for fid in sorted(mf):
        r = mf[fid]
        if r.get("durum") != "tamam":
            rows.append((fid, None, r.get("durum", "?")))
            continue
        d = diff.get(fid, {})
        rows.append((fid, r, d))

    print("| Ucus | Kare | Irtifa | Yol | Eslesme orani | Kapsama | Medyan | p90 |")
    print("|---|---|---|---|---|---|---|---|")
    meds, tuts = [], []
    for fid, r, d in rows:
        if r is None:
            print("| %s | — | — | — | — | — | — | *%s* |" % (fid, d))
            continue
        tut = d.get("tutma_orani")
        meds.append(r["medyan_m"])
        if tut is not None:
            tuts.append((tut, r["medyan_m"]))
        print("| %s | %d | %.0f m | %.0f km | %s | %%%.1f | **%.2f m** | %.2f m |" % (
            fid, r["kare"], r["irtifa_m"], r["km"],
            ("%%%.0f" % (tut * 100)) if tut is not None else "—",
            r["kapsama"] * 100, r["medyan_m"], r["p90_m"]))

    print()
    print("Degerlendirilen ucus: %d" % len(meds))
    print("Medyan hatalarin medyani: %.2f m (en iyi %.2f, en kotu %.2f)" % (
        np.median(meds), min(meds), max(meds)))

    if tuts:
        t = np.array([a for a, _ in tuts])
        m = np.array([b for _, b in tuts])
        ok, bad = t >= 0.5, t < 0.5
        print()
        print("ESIK ANALIZI (eslesme orani = gercek konumda >=40 ic nokta veren kare):")
        if ok.any():
            print("  >= %%50 eslesen %d ucus : medyan hata %.2f - %.2f m, medyani %.2f m"
                  % (ok.sum(), m[ok].min(), m[ok].max(), np.median(m[ok])))
        if bad.any():
            print("  <  %%50 eslesen %d ucus : medyan hata %.2f - %.2f m"
                  % (bad.sum(), m[bad].min(), m[bad].max()))
        print("  korelasyon (eslesme orani ~ log hata): %+.3f"
              % np.corrcoef(t, np.log10(m))[0, 1])

    out = {"n_ucus": len(meds), "medyan_medyan": float(np.median(meds)),
           "en_iyi": float(min(meds)), "en_kotu": float(max(meds))}
    (RES / "22_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

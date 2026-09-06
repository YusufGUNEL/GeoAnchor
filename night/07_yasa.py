"""Is the night failure a matcher problem or a content problem?

06 showed that every representation fails on the same 89% of frames. Two
readings of that, and they lead to completely different work:

  matcher problem   the shared structure is there and LoFTR/RoMa cannot find
                    it across modalities -> train a cross-modal matcher, days
                    of GPU on the train split
  content problem   those frames have no structure in common to find, because
                    bare desert looks like bare desert in both modalities ->
                    training buys little, and the honest result is a law

The daylight half of this project ended in exactly such a law: performance is
set not by the algorithm but by whether the imagery and the basemap depict a
recognisably similar world, and the fraction of frames that do can be measured
on a planned route before flying. If the same thing governs the night data,
that is not a weaker result than a trained matcher -- it is the same finding
extended to a second sensor, and it costs one CPU pass.

So: score each frame for how much structure it holds, using only measures that
need no matching and no ground truth, and ask whether that predicts which
frames get located correctly. Reported as AUC against the per-frame verdicts
already recorded in 03_dogrulama_1000.json.

The satellite measures carry the argument. A basemap is what you have before
the flight, so a satellite-side predictor is operationally the same kind of
statement as the daylight match rate: it turns "will this work here" into
something measurable in advance. The thermal measures are diagnostic -- they
say whether the sensor or the map is the limiting side.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

import cv2
import h5py
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "night"))
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

kopru = import_module("02_kopru")

DATA = ROOT / "night" / "veri" / "thermal_dataset"
OUT = ROOT / "night" / "sonuclar"
FIG = ROOT / "figures"
KAYIT = OUT / "03_dogrulama_1000.json"


def edge_density(g: np.ndarray) -> float:
    """Fraction of pixels Canny calls an edge. Thresholds from the image's own
    median, so it measures structure rather than absolute contrast."""
    v = float(np.median(g))
    lo, hi = int(max(0, 0.66 * v)), int(min(255, 1.33 * v))
    return float(cv2.Canny(cv2.GaussianBlur(g, (0, 0), 1.2), lo, hi).mean() / 255.0)


def gradient_energy(g: np.ndarray) -> float:
    """Mean gradient magnitude after the band-pass the matcher actually sees."""
    d = kopru.rep_dog_clahe(g, False)
    gx = cv2.Sobel(d, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(d, cv2.CV_32F, 0, 1, ksize=3)
    return float(cv2.magnitude(gx, gy).mean())


def high_frequency(g: np.ndarray) -> float:
    """Share of spectral energy above a quarter of Nyquist.

    Featureless ground is not dark, it is smooth: its energy sits at low
    spatial frequency. This separates "nothing there" from "dim".
    """
    f = np.fft.fftshift(np.fft.fft2(g.astype(np.float32) - g.mean()))
    p = np.abs(f) ** 2
    h, w = p.shape
    yy, xx = np.ogrid[:h, :w]
    r = np.hypot(yy - h / 2, xx - w / 2)
    total = p.sum()
    return float(p[r > min(h, w) / 8].sum() / total) if total > 0 else 0.0


def entropy(g: np.ndarray) -> float:
    """Shannon entropy of the band-passed image."""
    d = kopru.rep_dog_clahe(g, False)
    hist = np.bincount(d.ravel(), minlength=256).astype(np.float64)
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


OLCUTLER = {
    "kenar_yogunlugu": edge_density,
    "gradyan_enerjisi": gradient_energy,
    "yuksek_frekans": high_frequency,
    "entropi": entropy,
}


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order), dtype=float)
    ranks[order] = np.arange(1, len(order) + 1)
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2)
                 / (len(pos) * len(neg)))


def measure_frames(n: int) -> dict:
    """One pass over the images. The only expensive part, and it never changes."""
    with h5py.File(DATA / "test_database.h5", "r") as sat, \
         h5py.File(DATA / "test_queries.h5", "r") as thr:
        pairs = kopru.build_pairs(kopru.coords(sat), n)
        # 03 appends one row per pair and only skips a pair when the matcher
        # returns nothing, so equal counts is what lets row i mean pair i. If
        # that ever stops holding the join is silently wrong, hence the check.
        if len(pairs) != n:
            raise SystemExit(f"{len(pairs)} cift ama {n} kayit -- eslestirme guvenli degil")
        vals = {f"{side}_{name}": np.empty(n)
                for side in ("uydu", "termal") for name in OLCUTLER}
        for k, (i, j) in enumerate(pairs):
            t = kopru.gray(thr["image_data"][i])
            s_img = kopru.gray(sat["image_data"][j])
            for name, fn in OLCUTLER.items():
                vals[f"uydu_{name}"][k] = fn(s_img)
                vals[f"termal_{name}"][k] = fn(t)
            print(f"\r  {k + 1}/{n}", end="", flush=True)
    print("\n")
    return vals


def derive(ham: dict) -> dict:
    """Combinations built from the raw measures. Kept out of the cache so a
    change here takes effect without redoing the image pass."""
    def z(v):
        return (v - v.mean()) / (v.std() + 1e-9)

    vals = dict(ham)
    # You need structure on both sides, so the weaker side should be binding.
    for name in OLCUTLER:
        vals[f"zayif_taraf_{name}"] = np.minimum(z(ham[f"uydu_{name}"]),
                                                 z(ham[f"termal_{name}"]))

    # The two edge measures say opposite things about a tile and both matter:
    # coarse structure present, fine texture absent. Their difference is the
    # one number a mission planner would want, and it needs only the basemap.
    def yapi(side):
        return z(ham[f"{side}_kenar_yogunlugu"]) - z(ham[f"{side}_yuksek_frekans"])

    vals["uydu_yapi_skoru"] = yapi("uydu")
    vals["zayif_taraf_yapi_skoru"] = np.minimum(yapi("uydu"), yapi("termal"))
    return vals


def analyse(ham: dict, labels: np.ndarray, n: int) -> int:
    vals = derive(ham)

    # A measure that predicts failure is as useful as one that predicts
    # success -- it just points the other way. The first version of this script
    # ranked on the raw AUC and buried its own strongest result: the
    # high-frequency fraction scored 0.201, meaning 0.799 once inverted. Fine
    # texture (sand speckle, scrub) is not structure, and a tile full of it is
    # a tile with nothing large enough to match on.
    def strength(key):
        a = auc(vals[key], labels)
        return max(a, 1 - a)

    print("=" * 74)
    print(f"{'olcut':28s} {'AUC':>7s} {'yon':>6s}   {'dogru ort':>11s} {'yanlis ort':>11s}")
    print("-" * 74)
    summary = {}
    for key in sorted(vals, key=lambda k: -strength(k)):
        s = vals[key]
        a = auc(s, labels)
        yukari = a >= 0.5
        summary[key] = {"auc_ham": a, "auc": max(a, 1 - a),
                        "yon": "yuksek=iyi" if yukari else "DUSUK=iyi",
                        "dogru_ort": float(s[labels].mean()),
                        "yanlis_ort": float(s[~labels].mean())}
        print(f"{key:28s} {max(a, 1 - a):7.3f} {'+' if yukari else '-':>6s}   "
              f"{s[labels].mean():11.4f} {s[~labels].mean():11.4f}")
    print("=" * 74)
    print("yon '-' : olcut DUSUKKEN kare tutuyor. AUC ters cevrilmis degeri.")
    print("Karsilastirma (03'ten, esleme SONRASI olculen): ic nokta 0.803,")
    print("yon uyumu 0.878. Buradakiler esleme ONCESI, sadece goruntuden.")

    best = max(summary, key=lambda k: summary[k]["auc"])
    print(f"\nen guclu yordayici: {best}  AUC {summary[best]['auc']:.3f} "
          f"({summary[best]['yon']})")
    if summary[best]["auc"] >= 0.70:
        print("-> ICERIK sorunu: hangi karelerin tutacagini goruntunun kendisi")
        print("   soyluyor, eslesme denenmeden. Gunduzdeki yasanin gece karsiligi.")
    elif summary[best]["auc"] >= 0.60:
        print("-> kismi: icerik bir sey soyluyor ama tek basina aciklamiyor.")
    else:
        print("-> ESLEYICI sorunu: yapi orada, esleyici kipler arasi bulamiyor.")
        print("   Egitimli cross-modal esleyici gerekcelendi.")

    # Decile plot of the satellite-side winner: the operational statement is
    # about the basemap, so that is the curve worth drawing. Orientated so the
    # x axis always reads "more of this, more likely to work".
    sat_best = max((k for k in summary if k.startswith("uydu_")),
                   key=lambda k: summary[k]["auc"])
    x = vals[sat_best] if summary[sat_best]["auc_ham"] >= 0.5 else -vals[sat_best]
    edges = np.quantile(x, np.linspace(0, 1, 11))
    edges[-1] += 1e-9
    idx = np.clip(np.digitize(x, edges) - 1, 0, 9)
    rate = np.array([labels[idx == b].mean() * 100 if (idx == b).any() else np.nan
                     for b in range(10)])
    centres = np.array([x[idx == b].mean() if (idx == b).any() else np.nan
                        for b in range(10)])

    fig, axes = plt.subplots(1, 2, figsize=(14.6, 6.0),
                             gridspec_kw={"width_ratios": [1.25, 1]})

    ax = axes[0]
    cols = ["#ff2d55" if r < 100 * labels.mean() else "#00b894" for r in rate]
    ax.bar(np.arange(1, 11), rate, color=cols, edgecolor="k", linewidth=0.6)
    ax.axhline(100 * labels.mean(), color="#2d3436", ls="--", lw=1.3,
               label=f"genel ortalama %{100 * labels.mean():.1f}")
    for b, r in enumerate(rate):
        ax.text(b + 1, r + 0.8, f"%{r:.0f}", ha="center", fontsize=10)
    ax.set_xticks(np.arange(1, 11))
    ax.set_xlabel("uydu karosunun yapi icerigine gore decile\n"
                  "(1 = en yapisiz karolar, 10 = en yapili)")
    ax.set_ylabel("dogru konumlanan kare orani (%)")
    ax.set_ylim(0, max(rate[~np.isnan(rate)]) * 1.22)
    ax.set_title("En yapisiz onda birde HICBIR kare tutmuyor,\n"
                 "en yapilida her uc karenin biri", fontsize=12.5)
    ax.grid(alpha=0.25, axis="y")
    ax.legend(fontsize=10, loc="upper left")

    # The comparison that matters: this measure needs only the basemap, and it
    # still ranks with the scores that require the match to have been computed.
    ax = axes[1]
    bars = [
        ("yon uyumu", 0.878, "sonra"),
        (sat_best.replace("uydu_", "uydu karosu: "), summary[sat_best]["auc"], "once"),
        ("ic nokta sayisi", 0.803, "sonra"),
        ("uydu: yuksek frekans", summary["uydu_yuksek_frekans"]["auc"], "once"),
        ("uydu: kenar yogunlugu", summary["uydu_kenar_yogunlugu"]["auc"], "once"),
        ("karsilikli bilgi", 0.521, "sonra"),
    ]
    bars.sort(key=lambda b: b[1])
    y = np.arange(len(bars))
    ax.barh(y, [b[1] for b in bars],
            color=["#00b894" if b[2] == "once" else "#b2bec3" for b in bars],
            edgecolor="k", linewidth=0.6)
    for i, b in enumerate(bars):
        ax.text(b[1] + 0.006, i, f"{b[1]:.3f}", va="center", fontsize=10)
    ax.set_yticks(y)
    ax.set_yticklabels([b[0] for b in bars], fontsize=10)
    ax.axvline(0.5, color="#636e72", ls=":", lw=1.2)
    ax.set_xlim(0.45, 1.0)
    ax.set_xlabel("AUC — dogru fix'i yanlistan ayirma gucu")
    ax.set_title("YESIL: eslesmeden ONCE, sadece haritadan olculuyor\n"
                 "GRI: eslesme yapildiktan SONRA olculebiliyor", fontsize=12.5)
    ax.grid(alpha=0.25, axis="x")

    fig.suptitle("Gecede de basarimi belirleyen sey esleyici degil, KARONUN ICERIGI — "
                 f"{n} kare", fontsize=14, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    fig.savefig(FIG / "32_gece_yasa.png", dpi=125, bbox_inches="tight")
    plt.close(fig)
    print(f"-> {FIG / '32_gece_yasa.png'}")

    (OUT / f"07_yasa_{n}.json").write_text(json.dumps(
        {"n": n, "dogru": int(labels.sum()), "ozet": summary,
         "en_iyi": best, "en_iyi_uydu": sat_best,
         "decile": {"merkez": centres.tolist(), "dogru_orani": rate.tolist()},
         # Raw per-frame measures only: derived ones are rebuilt on load,
         # so editing derive() does not need another image pass.
         "ham_olcumler": {k: v.tolist() for k, v in ham.items()},
         "dogru_etiket": labels.tolist()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {OUT / f'07_yasa_{n}.json'}")
    return 0


def main() -> int:
    if not KAYIT.exists():
        raise SystemExit(f"{KAYIT.name} yok -- once: python night/03_dogrulama.py 1000")
    rows = json.loads(KAYIT.read_text(encoding="utf-8"))["kareler"]
    n = len(rows)
    labels = np.array([r["dogru"] for r in rows])
    print(f"{n} kare, {labels.sum()} dogru (%{100 * labels.mean():.1f})\n", flush=True)

    # The image pass costs minutes and its result never changes, so a previous
    # run's raw measures are reused. --yenile forces a recompute.
    cache = OUT / f"07_yasa_{n}.json"
    ham = None
    if cache.exists() and "--yenile" not in sys.argv:
        prev = json.loads(cache.read_text(encoding="utf-8")).get("ham_olcumler")
        if prev and all(len(v) == n for v in prev.values()):
            print(f"onbellek: {cache.name}\n")
            ham = {k: np.array(v) for k, v in prev.items()}
    if ham is None:
        ham = measure_frames(n)
    return analyse(ham, labels, n)


if __name__ == "__main__":
    raise SystemExit(main())

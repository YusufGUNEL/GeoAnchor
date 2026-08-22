"""Tek bir ucusu bastan sona hazirlayan ve degerlendiren boru hatti.

Ucus 03 uzerinde elle yurutulen adimlarin genellestirilmis hali. Ucuslar
birbirinden ciddi bicimde farkli oldugu icin hicbir sabit varsayilmiyor:

  - irtifa ucustan ucusa degisiyor (cok pervaneli alcak ucus vs sabit kanat
    yuksek ucus) -> IHA yer ornekleme araligi HER UCUS icin ayri kestiriliyor
  - kamera/montaj farkli olabilir -> boresight HER UCUSTA ayri kalibre ediliyor
  - uydu haritalari farkli boyutta -> karo izgarasi haritaya gore kuruluyor

Kalibrasyonlar her zaman ucusun ILK %20'sinde yapilip kalan %80'de olculuyor.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np

from .flight import load_flight, Flight
from .geo import SatelliteMap, haversine_m, meters_per_degree
from .geometry import AttitudeModel, calibrate, body_from_ne
from .features import Dinov2Embedder
from .tiles import build_tile_grid
from .matching import LoFTRMatcher
from .localize import SingleFrameLocalizer
from .odometry import VisualOdometry
from .particle_filter import PFConfig
from .preprocess import drone_to_northup
from .sequential import SequentialLocalizer

TILE_M, STRIDE_M, OUT_PX = 300.0, 150.0, 640
CROP_M = 400.0
CAL_FRAC = 0.20


@dataclass
class FlightPrep:
    """Bir ucus icin hazirlanan her sey."""
    flight_id: str
    n_frames: int
    drone_gsd: float
    mean_height: float
    dist_km: float
    step_m: float
    map_km2: float
    n_tiles: int
    att: AttitudeModel
    cal_median_before: float
    cal_median_after: float


def estimate_drone_gsd(flight: Flight, n_pairs: int = 16) -> float:
    """IHA goruntusunun metre/piksel olcegi, ardisik kare eslemesinden.

    Iki ardisik kare arasindaki kayma piksel cinsinden eslemeyle, metre
    cinsinden gercek konumdan bilinir; oran olcegi verir. Irtifa ve kamera
    ucustan ucusa degistigi icin bu HER UCUS icin yeniden yapilmali.
    """
    sift = cv2.SIFT_create(nfeatures=3000)
    bf = cv2.BFMatcher()
    ratios = []
    idxs = np.linspace(0, flight.n_frames - 2, n_pairs * 3).astype(int)
    for i in idxs:
        if len(ratios) >= n_pairs:
            break
        if abs(float(flight.df["Phi1"].iloc[i + 1] - flight.df["Phi1"].iloc[i])) > 5:
            continue
        step_m = float(flight.df["step_m"].iloc[i + 1])
        if step_m < 5:
            continue
        im1 = cv2.imread(str(flight.image_path(i)), cv2.IMREAD_GRAYSCALE)
        im2 = cv2.imread(str(flight.image_path(i + 1)), cv2.IMREAD_GRAYSCALE)
        if im1 is None or im2 is None:
            continue
        s = 0.25
        a = cv2.resize(im1, None, fx=s, fy=s)
        b = cv2.resize(im2, None, fx=s, fy=s)
        k1, d1 = sift.detectAndCompute(a, None)
        k2, d2 = sift.detectAndCompute(b, None)
        if d1 is None or d2 is None:
            continue
        good = [m for m, n in bf.knnMatch(d1, d2, k=2) if m.distance < 0.75 * n.distance]
        if len(good) < 30:
            continue
        p1 = np.float32([k1[m.queryIdx].pt for m in good])
        p2 = np.float32([k2[m.trainIdx].pt for m in good])
        M, mask = cv2.estimateAffinePartial2D(p1, p2, cv2.RANSAC,
                                              ransacReprojThreshold=3.0)
        if M is None or mask is None or mask.sum() < 20:
            continue
        shift = float(np.hypot(M[0, 2], M[1, 2])) / s
        if shift < 1:
            continue
        ratios.append(step_m / shift)
    return float(np.median(ratios)) if ratios else float("nan")


def cache_northup(flight: Flight, sat: SatelliteMap, gsd: float,
                  cache_dir: Path) -> np.ndarray:
    """Kuzey-yukari, uydu olcegine indirilmis kareleri diske yazar."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"northup_{flight.flight_id}_{OUT_PX}.npy"
    if p.exists():
        return np.load(p, mmap_mode="r")
    arr = np.lib.format.open_memmap(p, mode="w+", dtype=np.uint8,
                                    shape=(flight.n_frames, OUT_PX, OUT_PX, 3))
    for i in range(flight.n_frames):
        im = cv2.imread(str(flight.image_path(i)))
        nu = drone_to_northup(im, float(flight.df["Phi1"].iloc[i]), gsd,
                              sat.gsd, TILE_M, yaw_sign=-1.0, out_px=OUT_PX)
        arr[i] = cv2.cvtColor(nu, cv2.COLOR_BGR2RGB)
    arr.flush()
    return np.load(p, mmap_mode="r")


def build_tiles(sat: SatelliteMap, emb: Dinov2Embedder, cache_dir: Path,
                flight_id: str):
    """Karo izgarasi + gomme veritabani (varsa yeniden uretmez)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"tiles_{flight_id}.npz"
    if p.exists():
        z = np.load(p)
        return z["lat"], z["lon"], z["emb"]
    x0, y0, lat, lon, tile_px, grid = build_tile_grid(sat, TILE_M, STRIDE_M)
    n = len(x0)
    out = np.zeros((n, emb.dim), dtype=np.float32)
    buf, idx = [], []
    for i in range(n):
        t = sat.read_window(int(x0[i]), int(y0[i]), tile_px, tile_px)
        buf.append(cv2.resize(t, (448, 448), interpolation=cv2.INTER_AREA))
        idx.append(i)
        if len(buf) == 24 or i == n - 1:
            out[idx] = emb.embed(np.stack(buf), batch=24)
            buf, idx = [], []
    np.savez_compressed(p, lat=lat, lon=lon, emb=out)
    return lat, lon, out


def embed_queries(q: np.ndarray, emb: Dinov2Embedder, cache_dir: Path,
                  flight_id: str) -> np.ndarray:
    p = cache_dir / f"qemb_{flight_id}.npy"
    if p.exists():
        return np.load(p)
    outs = []
    for i in range(0, len(q), 24):
        outs.append(emb.embed(np.ascontiguousarray(q[i:i + 24]), batch=24))
    v = np.concatenate(outs, 0)
    np.save(p, v)
    return v


def calibrate_boresight(flight: Flight, sat: SatelliteMap, q, matcher, gsd):
    """Ucusun ilk %20'sinde kamera montaj sapmasini olcer.

    IKI KORUMA VAR, ikisi de olcumle gerekli oldugu gorulduğu icin eklendi:

    1) ETKIN IRTIFA. Model "yerdeki kayma = irtifa x tan(aci)" diyor ve kayitli
       yuksekligi kullaniyor. Ama o yukseklik her ucusta gercek YERDEN yukseklik
       olmayabilir (deniz seviyesine gore olcum, farkli referans, vb).
       Ucus 05'te (kayitli 2313 m) duzeltme hatayi 27,8 m'den 131,2 m'ye
       CIKARDI. Bu yuzden etkin irtifa da veriden kestiriliyor.

    2) ZARAR VERME KURALI. Kalibrasyon kareleri ikiye bolunuyor: yarisinda
       uyduruluyor, digerinde sinaniyor. Duzeltme sinama yarisinda hatayi
       AZALTMIYORSA hic uygulanmiyor. Ise yaramayan bir duzeltmeyi uygulamak,
       hic duzeltme yapmamaktan kotudur.
    """
    n_cal = max(12, int(flight.n_frames * CAL_FRAC))
    idxs = np.linspace(0, n_cal - 1, min(48, n_cal)).astype(int)
    m_lat, m_lon = meters_per_degree(sat.center_lat)
    dn, de, keep = [], [], []
    for i in idxs:
        r = flight.df.iloc[i]
        crop_rgb, x0, y0, _ = sat.crop_meters(float(r.lat), float(r.lon),
                                              CROP_M, OUT_PX)
        crop = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
        qg = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        pa, pb, _ = matcher.match(qg, crop)
        if len(pa) < 30:
            continue
        H, mask = cv2.findHomography(pa.astype(np.float32), pb.astype(np.float32),
                                     cv2.USAC_MAGSAC, 4.0, maxIters=10_000,
                                     confidence=0.999)
        if H is None or mask is None or mask.sum() < 30:
            continue
        p = H @ np.array([OUT_PX / 2, OUT_PX / 2, 1.0])
        if abs(p[2]) < 1e-9:
            continue
        u, v = p[0] / p[2], p[1] / p[2]
        mx, my = sat.out_px_to_map_px(u, v, x0, y0, CROP_M, OUT_PX)
        plat, plon = sat.px_to_latlon(mx, my)
        dn.append((float(plat) - float(r.lat)) * m_lat)
        de.append((float(plon) - float(r.lon)) * m_lon)
        keep.append(i)

    none = AttitudeModel()
    if len(dn) < 12:
        return none, float("nan"), float("nan"), len(dn)

    sub = flight.df.iloc[keep]
    fwd, rgt = body_from_ne(np.array(dn), np.array(de), sub["Phi1"].values)
    # KANAL DUZELTMESI: Kappa = egim, Omega = yalpa (deneyle belirlendi)
    pitch = sub["Kappa"].values
    roll = sub["Omega"].values
    h_rec = sub["height"].values

    # --- etkin irtifa: kaymanin buyuklugu ile tan(aci) arasindaki oran ---
    ang = np.hypot(np.tan(np.radians(pitch)), np.tan(np.radians(roll)))
    mag = np.hypot(fwd, rgt)
    sel = ang > np.radians(0.4)          # cok kucuk acilar gurultulu, disla
    h_eff = h_rec
    if sel.sum() >= 6:
        k = float(np.median(mag[sel] / (ang[sel] * h_rec[sel])))
        if 0.05 < k < 20.0:
            h_eff = h_rec * k

    # --- fit / sinama bolunmesi ---
    n = len(fwd)
    fit = np.arange(n) % 2 == 0
    tst = ~fit
    best, best_err = none, float(np.median(np.hypot(fwd[tst], rgt[tst])))
    base_err = best_err
    for h_try, lbl in [(h_eff, "etkin"), (h_rec, "kayitli")]:
        att = calibrate(fwd[fit], rgt[fit], pitch[fit], roll[fit], h_try[fit])
        if abs(att.pitch_bias_deg) > 15 or abs(att.roll_bias_deg) > 15:
            continue
        pf, pr = att.offset_body(pitch[tst], roll[tst], h_try[tst])
        err = float(np.median(np.hypot(fwd[tst] - pf, rgt[tst] - pr)))
        if err < best_err:
            best, best_err = att, err
    if best is not none:
        best.height_scale = float(np.median(h_eff / h_rec))
    return best, base_err, best_err, n
def run_odometry(q, gsd_out_px: float, flight: Flight):
    """Ardisik kareler arasi bagil hareket (kuzey-yukari kirpmalar uzerinde)."""
    vo = VisualOdometry(m_per_px=TILE_M / OUT_PX)
    dn = np.full(flight.n_frames - 1, np.nan)
    de = np.full(flight.n_frames - 1, np.nan)
    prev = cv2.cvtColor(np.ascontiguousarray(q[0]), cv2.COLOR_RGB2GRAY)
    for i in range(1, flight.n_frames):
        curr = cv2.cvtColor(np.ascontiguousarray(q[i]), cv2.COLOR_RGB2GRAY)
        s = vo.step(prev, curr)
        if s.ok:
            dn[i - 1], de[i - 1] = s.d_north_m, s.d_east_m
        prev = curr
    return dn, de

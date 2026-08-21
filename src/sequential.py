"""Faz 3 — sıralı konumlandırma: odometri + uydu eşlemesi + parçacık süzgeci.

Tek kare yaklaşımının iki derdi vardır:
  1. Karelerin önemli kısmında eşleme hiç tutmaz (su, tekdüze tarla, tekrar
     eden yapı deseni) — o karede konum YOKTUR.
  2. Tuttuğunda bile arada bir tamamen yanlış yeri gösterir.

Sıralı sistem ikisini de çözer:
  - Eşleme tutmayan karede odometri devam eder, konum kesilmez.
  - Yanlış ölçüm uçuşun geri kalanıyla tutarsız kalır ve süzgeç bastırır.

Üstelik daha HIZLIDIR: nerede olduğumuzu kabaca bildiğimiz için haritanın
tamamında 8 aday denemek yerine tek bir yere bakmak yeter.

ÇEVRİMİÇİ PUSULA KALİBRASYONU
Homografinin dönme bileşeni, İHA karesi kuzeye göre ne kadar yanlış
döndürüldüğünü söyler — yani yönelim açısının hatasını. Ölçüldü: bu hata uçuş
koluna göre değişiyor (−1,9° ve −7,1°), manyetometrenin sert-demir hatasının
klasik imzası. Sistem bu sapmayı harita eşlemelerinden kendisi öğrenip
odometri artışlarını düzeltiyor. Hiçbir GPS/gerçek konum bilgisi kullanılmıyor.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from .geo import SatelliteMap, local_m_to_latlon, latlon_to_local_m
from .geometry import AttitudeModel
from .localize import SingleFrameLocalizer
from .particle_filter import (Candidate, ParticleFilter, PFConfig,
                              sigma_from_inliers, weight_from_inliers)


@dataclass
class StepResult:
    """Bir karenin sıralı işlenme sonucu."""
    north: float = float("nan")
    east: float = float("nan")
    spread: float = float("nan")
    n_loftr: int = 0
    measured: bool = False
    inliers: int = 0
    relocalized: bool = False
    mode: str = ""
    yaw_bias: float = float("nan")
    scale_corr: float = float("nan")
    meas_north: float = float("nan")   # ham olcum (suzgecten gecmemis) — teshis
    meas_east: float = float("nan")
    pred_north: float = float("nan")   # olcum oncesi tahmin — teshis
    pred_east: float = float("nan")
    ms: float = 0.0


class SequentialLocalizer:
    """Odometri ile uydu eşlemesini parçacık süzgecinde birleştirir."""

    def __init__(self, sat: SatelliteMap, loc: SingleFrameLocalizer,
                 att: AttitudeModel, lat0: float, lon0: float,
                 pf_cfg: PFConfig | None = None,
                 local_min_inliers: int = 40,
                 gate_m: float = 120.0,
                 nearby_radius_m: float = 400.0,
                 max_nearby: int = 3,
                 quality_target: int = 150,
                 reloc_cooldown: int = 4,
                 yaw_window: int = 12,
                 use_online_yaw: bool = True,
                 use_online_scale: bool = True,
                 expected_scale: float = 0.75,
                 seed: int = 0):
        self.sat = sat
        self.loc = loc
        self.att = att
        self.lat0, self.lon0 = lat0, lon0
        self.pf = ParticleFilter(pf_cfg or PFConfig(),
                                 rng=np.random.default_rng(seed))
        self.local_min_inliers = local_min_inliers
        self.gate_m = gate_m
        self.nearby_radius_m = nearby_radius_m
        self.max_nearby = max_nearby
        self.quality_target = quality_target
        self.reloc_cooldown = reloc_cooldown
        self._since_reloc = 999
        self.use_online_yaw = use_online_yaw
        self.use_online_scale = use_online_scale
        self.expected_scale = expected_scale
        self.yaw_hist: deque[float] = deque(maxlen=yaw_window)
        self.scale_hist: deque[float] = deque(maxlen=yaw_window)
        self.yaw_bias = 0.0
        self.scale_corr = 1.0
        self.last_step = (0.0, 0.0)      # ölü hesap için son bilinen hareket
        # Ölü hesap için hız ve rota sapması: İHA'nın burnunun baktığı yön ile
        # yer üstünde gerçekten ilerlediği yön rüzgâr yüzünden farklıdır
        # (yengeç açısı). Bu fark başarılı adımlardan öğrenilir.
        self.speed_hist: deque[float] = deque(maxlen=10)
        self.course_hist: deque[float] = deque(maxlen=10)
        self.last_speed = 96.0
        self.course_offset = 0.0
        self.disagree_count = 0          # ölçüm inanışla kaç karedir uyuşmuyor
        tn, te = latlon_to_local_m(loc.tile_lat, loc.tile_lon, lat0, lon0)
        self.tile_n, self.tile_e = np.asarray(tn), np.asarray(te)

    # --- dönüşüm yardımcıları ---
    def to_latlon(self, north, east):
        return local_m_to_latlon(north, east, self.lat0, self.lon0)

    def to_local(self, lat, lon):
        return latlon_to_local_m(lat, lon, self.lat0, self.lon0)

    # --- çevrimiçi pusula kalibrasyonu ---
    def _note_angle(self, ang: float):
        """Başarılı bir eşlemenin artık dönmesini kaydet ve sapmayı güncelle."""
        if np.isfinite(ang) and abs(ang) < 30.0:
            self.yaw_hist.append(float(ang))
            if len(self.yaw_hist) >= 3:
                self.yaw_bias = float(np.median(self.yaw_hist))

    def _note_motion(self, dn: float, de: float, yaw_deg: float):
        """Başarılı odometri adımından hız ve rota sapmasını öğren."""
        mag = float(np.hypot(dn, de))
        if mag < 5.0:
            return
        self.speed_hist.append(mag)
        self.last_speed = float(np.median(self.speed_hist))
        course = float(np.degrees(np.arctan2(de, dn)))
        self.course_hist.append((course - yaw_deg + 180) % 360 - 180)
        self.course_offset = float(np.median(self.course_hist))

    def _dr_step(self, yaw_deg: float):
        """Ölü hesap adımı: yön ataletsel birimden, hız son ölçümlerden.

        Önceki sürüm son hareket VEKTÖRÜNÜ tekrarlıyordu. Bu düz uçuşta iyi
        çalışıyor ama DÖNÜŞTE çöküyor: eski yönü sürdürüp İHA'yı haritada
        yanlış tarafa götürüyor. Ölçüldü — kopmaların hepsi (kare 192, 288,
        576) tam da tarama deseninin dönüş noktalarındaydı ve hata 250-560 m'ye
        çıkıyordu. Oysa yönelim ataletsel birimden her an biliniyor; sadece
        hızı ve rüzgâr kaynaklı yengeç açısını hatırlamak yeter.
        """
        th = np.radians(yaw_deg + self.course_offset)
        return self.last_speed * np.cos(th), self.last_speed * np.sin(th)

    def _note_scale(self, sc: float):
        """Eşlemenin ölçek bileşeninden İHA yer örnekleme aralığını düzelt.

        Sorgu kırpması 300 m'yi 640 piksele, uydu kırpması 400 m'yi 640 piksele
        sığdırıyor; dolayısıyla doğru ölçek 300/400 = 0,75 olmalı. Ölçülen ölçek
        bundan saparsa, varsayılan İHA yer örnekleme aralığı (0,1142 m/piksel)
        o oranda yanlış demektir — arazi yüksekliği değiştikçe olan tam da bu.
        Odometri bu aralıkla metreye çevrildiği için düzeltme oraya uygulanır.
        """
        if np.isfinite(sc) and 0.4 < sc < 1.3:
            self.scale_hist.append(float(sc) / self.expected_scale)
            if len(self.scale_hist) >= 3:
                self.scale_corr = float(np.median(self.scale_hist))

    def _rotate_step(self, d_north: float, d_east: float):
        """Odometri artışını öğrenilen pusula sapması ve ölçekle düzelt."""
        k = self.scale_corr if self.use_online_scale else 1.0
        d_north, d_east = d_north * k, d_east * k
        if not self.use_online_yaw or self.yaw_bias == 0.0:
            return d_north, d_east
        t = np.radians(self.yaw_bias)
        c, s = np.cos(t), np.sin(t)
        return d_north * c - d_east * s, d_north * s + d_east * c

    # --- ölçüm üretimi ---
    def _measure_at(self, qg, north, east, pitch, roll, height, yaw):
        """Belirli bir yerel konumda uydu eşlemesi dene."""
        lat, lon = self.to_latlon(north, east)
        la, lo, n, _, sc, ang = self.loc.match_at(qg, float(lat), float(lon))
        if la is None or n < self.local_min_inliers:
            return None, n, float("nan")
        self._note_scale(sc)
        cla, clo = self.loc.apply_attitude(la, lo, pitch, roll, height, yaw)
        cn, ce = self.to_local(cla, clo)
        return Candidate(north=float(cn), east=float(ce),
                         weight=weight_from_inliers(n),
                         sigma=sigma_from_inliers(n)), n, ang

    def _nearby_tiles(self, north, east, radius_m, k):
        """Tahmin çevresindeki karolar, yakınlık sırasına göre."""
        d2 = (self.tile_n - north) ** 2 + (self.tile_e - east) ** 2
        m = np.where(d2 <= radius_m ** 2)[0]
        return m if len(m) <= k else m[np.argsort(d2[m])[:k]]

    # --- ana adım ---
    def step(self, qg, qemb, pitch, roll, height, yaw,
             d_north=None, d_east=None, expected_step_m: float = 96.0) -> StepResult:
        """Bir kareyi işler ve güncel konum kestirimini döndürür."""
        res = StepResult()

        # 1) İLK KARE: hiçbir öncül yok, haritanın tamamında ara.
        if not self.pf.initialized:
            f = self.loc.localize(qg, qemb, pitch, roll, height, yaw)
            res.n_loftr += f.n_tried
            res.relocalized = True
            res.mode = "yeniden konumlanma"
            if f.ok:
                n_, e_ = self.to_local(f.lat, f.lon)
                self.pf.initialize(float(n_), float(e_),
                                   sigma_m=sigma_from_inliers(f.inliers) * 2)
                self._note_angle(f.angle)
                res.measured = True
                res.inliers = f.inliers
                res.north, res.east = self.pf.estimate()
                res.spread = self.pf.spread()
            res.yaw_bias = self.yaw_bias
            return res

        # 2) tahmin: pusula duzeltmeli odometri artisi
        #
        # ÖNEMLİ: tahmin HER ZAMAN yapılır — süzgeç kendini kaybetmiş olsa bile.
        # Önceki sürümde "kayıp" durumu ayrı bir dala sapıyor ve eldeki geçerli
        # odometriyi tamamen atıyordu. Ölçüldü: eşlemenin çöktüğü bölgelerde
        # (su üstü, tekdüze arazi) odometri aslında SAĞLAMDI — adım hatası
        # 8,6 m, yani normalle aynı — ama kullanılmadığı için hata 630 m'ye
        # çıkıyordu. Yeniden konumlanma, hareket modelinin yerine geçen bir şey
        # değil, ek bir ölçüm denemesidir.
        if d_north is not None and np.isfinite(d_north):
            dn, de = self._rotate_step(float(d_north), float(d_east))
            self.pf.predict(dn, de)
            self.last_step = (dn, de)
            self._note_motion(dn, de, yaw)
        else:
            # odometri kaçtı: yönü ataletsel birimden, hızı geçmişten al
            self.pf.dead_reckon(*self._dr_step(yaw))

        pn, pe = self.pf.estimate()
        # Kapı genişliği belirsizliğe göre ayarlanır: süzgeç emin değilse
        # uzaktaki ölçümleri de kabul etmeli, yoksa kendini toparlayamaz.
        gate = float(np.clip(3.0 * self.pf.spread(), self.gate_m, 400.0))

        # 3) olcum: once tam tahmin edilen yere bak (tek LoFTR cagrisi)
        cands = []
        c, n_in, ang = self._measure_at(qg, pn, pe, pitch, roll, height, yaw)
        res.n_loftr += 1
        res.pred_north, res.pred_east = pn, pe
        if c is not None:
            res.meas_north, res.meas_east = c.north, c.east
        if c is not None and np.hypot(c.north - pn, c.east - pe) <= gate:
            cands.append(c)
            res.inliers = n_in
            self._note_angle(ang)

        # 4) Eşleme hiç tutmadıysa YA DA zayıf tuttuysa yakın karoları da dene.
        # "Zayıf tuttuysa" kısmı önemli: tek kare boru hattı ~4 adayın en
        # iyisini seçtiği için medyan 511 iç nokta yakalıyor; buradaki ilk
        # tutan adayda durma stratejisi 332'de kalıyordu. Bulunan ek adaylar
        # atılmıyor — parçacık süzgecinin olabilirliği zaten çok tepeli,
        # birden fazla adayı aynı anda taşıyabiliyor.
        if not cands or res.inliers < self.quality_target:
            for ti in self._nearby_tiles(pn, pe, self.nearby_radius_m, self.max_nearby):
                c2, n2, a2 = self._measure_at(qg, float(self.tile_n[ti]),
                                              float(self.tile_e[ti]),
                                              pitch, roll, height, yaw)
                res.n_loftr += 1
                if c2 is not None and np.hypot(c2.north - pn, c2.east - pe) <= gate:
                    cands.append(c2)
                    if n2 > res.inliers:
                        res.inliers = n2
                        res.meas_north, res.meas_east = c2.north, c2.east
                    self._note_angle(a2)
                    if res.inliers >= self.quality_target:
                        break

        # 4b) Yakın çevrede hiçbir şey bulunamadı VE süzgeç kendini kaybettiyse:
        # haritanın tamamında ara. Bu, hareket modelinin yerine geçmez —
        # tahmin yukarıda zaten yapıldı, bu sadece ek bir ölçüm denemesi.
        # Soğuma süresi var: eşlemenin çalışmadığı arazide (su üstü) her karede
        # 8 aday denemek boşuna 8 kat maliyet demek.
        if (not cands and self.pf.is_lost()
                and self._since_reloc >= self.reloc_cooldown):
            self._since_reloc = 0
            f = self.loc.localize(qg, qemb, pitch, roll, height, yaw)
            res.n_loftr += f.n_tried
            res.relocalized = True
            if f.ok:
                n_, e_ = self.to_local(f.lat, f.lon)
                # Ölçümü doğrudan dayatmak yerine aday olarak ver: yanlışsa
                # süzgeç onu yine de eleyebilsin.
                cands.append(Candidate(north=float(n_), east=float(e_),
                                       weight=weight_from_inliers(f.inliers),
                                       sigma=sigma_from_inliers(f.inliers)))
                self.pf.inject(cands)
                res.inliers = f.inliers
                res.mode = "yeniden konumlanma"
                self._note_angle(f.angle)
        else:
            self._since_reloc += 1

        # Uyuşmazlık takibi: ölçüm sürekli inanıştan uzak düşüyorsa, inanış
        # yanlıştır (erken bir hatalı eşleşmeye kilitlenmiş olabilir).
        # Bu durumda ölçüme atlamak doğrusudur — enjeksiyon yavaş kalırsa
        # güvenlik ağı olarak devreye girer.
        cfg = self.pf.cfg
        if c is not None:
            far = np.hypot(c.north - pn, c.east - pe)
            if far > cfg.disagree_m:
                self.disagree_count += 1
            else:
                self.disagree_count = 0
            if self.disagree_count >= cfg.disagree_patience:
                self.pf.initialize(c.north, c.east, sigma_m=max(10.0, c.sigma))
                self.disagree_count = 0
                if c not in cands:
                    cands = [c]
                res.mode = "olcume atlandi"
                self._note_angle(ang)

        res.measured = self.pf.update(cands)
        if not res.mode:
            res.mode = "izleme" if res.measured else "sadece odometri"
        res.north, res.east = self.pf.estimate()
        res.spread = self.pf.spread()
        res.yaw_bias = self.yaw_bias
        res.scale_corr = self.scale_corr
        return res

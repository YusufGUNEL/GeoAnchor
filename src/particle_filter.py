"""Parçacık süzgeci: görsel odometri ile uydu eşlemesini birleştirir.

Neden Kalman değil de parçacık süzgeci:
Uydu eşlemesinin hata dağılımı Gauss değil. Çoğu zaman doğru yeri birkaç metre
hatayla bulur; ama arada bir tamamen başka bir yeri gösterir (benzer tarla,
benzer kavşak, aynı desende ikinci bir mahalle). Yani ölçüm dağılımı
**çok tepeli** ve **ağır kuyruklu**. Kalman süzgeci tek tepeli Gauss varsayar
ve böyle bir aykırı ölçüm onu kalıcı olarak yanlış yere çeker.

Parçacık süzgeci bu iki durumu doğal biçimde taşır:
  - birden çok aday konumu aynı anda canlı tutar, zamanla hangisinin uçuşla
    tutarlı olduğuna karar verir,
  - olabilirliğe düz bir "aykırı değer tabanı" eklenerek saçma bir ölçümün
    tüm ağırlığı silip süpürmesi engellenir.

Durum: (kuzey, doğu) metre, yerel düzlemde. Yönelim ataletsel birimden,
ölçek altimetreden geldiği için duruma girmiyor.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Candidate:
    """Uydu eşlemesinden gelen tek bir aday konum."""
    north: float
    east: float
    weight: float          # güven (iç nokta sayısından türetilir)
    sigma: float           # bu adayın konum belirsizliği (m)


@dataclass
class PFConfig:
    n_particles: int = 600
    # Hareket modeli gürültüsü ÖLÇÜLEN odometri doğruluğuna oturtuldu:
    # ham odometrinin adım hatası medyanı 8,7 m (bkz results/06_odometry.json).
    # Önceki 3,1 m'lik değer süzgecin odometriye aşırı güvenmesine, dolayısıyla
    # doğru ölçümleri kapı dışında bırakıp sürüklenmesine yol açıyordu.
    motion_sigma_m: float = 3.0          # adım başına yalıtkan gürültü
    motion_sigma_frac: float = 0.06      # adım uzunluğuna oranlı bileşen
    dr_sigma_m: float = 15.0             # odometri kaçtığında ölü hesap gürültüsü
    # ölçüm modeli
    outlier_floor: float = 0.15          # olabilirlik tabanı (aykırı ölçüme karşı)
    min_sigma_m: float = 3.0
    max_sigma_m: float = 30.0
    # yeniden örnekleme
    ess_frac: float = 0.5                # etkin parçacık oranı bu altına inince
    # ölçüm güdümlü enjeksiyon (bkz ParticleFilter.inject)
    inject_frac: float = 0.30
    # kaybolma tespiti
    lost_spread_m: float = 250.0         # parçacık yayılımı bunu aşarsa kayıp
    lost_patience: int = 8               # bu kadar ardışık ölçümsüz kare -> kayıp
    disagree_m: float = 40.0             # ölçüm inanıştan bu kadar uzaksa "uyuşmazlık"
    disagree_patience: int = 5           # bu kadar ardışık uyuşmazlık -> ölçüme atla


class ParticleFilter:
    """İki boyutlu konum için ağırlıklı parçacık kümesi."""

    def __init__(self, cfg: PFConfig, rng: np.random.Generator | None = None):
        self.cfg = cfg
        self.rng = rng or np.random.default_rng(0)
        self.p = np.zeros((cfg.n_particles, 2))     # (kuzey, doğu)
        self.w = np.full(cfg.n_particles, 1.0 / cfg.n_particles)
        self.initialized = False
        self.no_meas_count = 0

    # --- kurulum ---
    def initialize(self, north: float, east: float, sigma_m: float = 20.0):
        n = self.cfg.n_particles
        self.p = np.stack([
            self.rng.normal(north, sigma_m, n),
            self.rng.normal(east, sigma_m, n)], axis=1)
        self.w = np.full(n, 1.0 / n)
        self.initialized = True
        self.no_meas_count = 0

    # --- tahmin ---
    def predict(self, d_north: float, d_east: float):
        """Odometri artışını uygula, üstüne süreç gürültüsü ekle."""
        step = float(np.hypot(d_north, d_east))
        s = self.cfg.motion_sigma_m + self.cfg.motion_sigma_frac * step
        n = len(self.p)
        self.p[:, 0] += d_north + self.rng.normal(0.0, s, n)
        self.p[:, 1] += d_east + self.rng.normal(0.0, s, n)

    def dead_reckon(self, d_north: float, d_east: float, sigma: float | None = None):
        """Odometri kaçtı: son bilinen hareketi sürdür, gürültüyü biraz büyüt.

        Önceki sürüm burada 96 m'lik kör gürültü basıyordu (bir kare boyunca
        alınan yol kadar). Bu, tek bir kaçan adımda parçacık bulutunu 130 m'ye
        yayıp süzgeci düşürüyordu. Oysa yönelim ataletsel birimden biliniyor ve
        hız neredeyse sabit — son adımı sürdürmek çok daha iyi bir tahmin.
        """
        n = len(self.p)
        s = self.cfg.dr_sigma_m if sigma is None else sigma
        self.p[:, 0] += d_north + self.rng.normal(0.0, s, n)
        self.p[:, 1] += d_east + self.rng.normal(0.0, s, n)

    def inject(self, cands: list["Candidate"]):
        """Parçacıkların bir kısmını ölçümün etrafına yeniden yerleştir.

        NEDEN GEREKLİ: parçacık bulutu birkaç metreye toplandığında, 100 m
        uzaktaki bir ölçüme HİÇBİR parçacık yakın olmaz; olabilirlik her yerde
        sıfıra iner ve ağırlıklar değişmez. Süzgeç doğru ölçümü görse bile
        yerinden kıpırdayamaz. Ölçüldü: erken bir yanlış eşleşmeye kilitlenen
        süzgeç, sonraki 20 karede gelen 4-10 m'lik doğru ölçümlere rağmen
        105 m hatada takılı kaldı.

        Çözüm, küresel konumlandırmada standart olan karma öneri dağılımı:
        her adımda parçacıkların küçük bir kısmı hareket modeli yerine ÖLÇÜM
        dağılımından çekilir. Ölçüm doğruysa bu parçacıklar yüksek ağırlık alır
        ve yeniden örneklemede bulutu kendine çeker; ölçüm yanlışsa düşük
        ağırlık alıp elenir. İzleme iyi giderken ölçüm zaten inanışa yakın
        olduğu için enjeksiyonun bir zararı olmaz.
        """
        if not cands or self.cfg.inject_frac <= 0:
            return
        n = len(self.p)
        k = max(1, int(round(self.cfg.inject_frac * n)))
        idx = self.rng.choice(n, size=k, replace=False)
        wts = np.array([c.weight for c in cands], dtype=float)
        wts = wts / wts.sum()
        pick = self.rng.choice(len(cands), size=k, p=wts)
        for j, ci in zip(idx, pick):
            c = cands[ci]
            s = float(np.clip(c.sigma, self.cfg.min_sigma_m, self.cfg.max_sigma_m))
            self.p[j, 0] = c.north + self.rng.normal(0.0, s)
            self.p[j, 1] = c.east + self.rng.normal(0.0, s)
            self.w[j] = self.w.mean()

    # --- güncelleme ---
    def update(self, cands: list[Candidate]) -> bool:
        """Aday konumlardan olabilirlik hesaplayıp ağırlıkları günceller.

        Çok tepeli ölçüm: adaylar üzerinden ağırlıklı toplam alınır, üstüne
        düz bir taban eklenir. Taban sayesinde hiçbir adaya yakın olmayan
        parçacıklar tamamen silinmez — yanlış bir ölçüm süzgeci kaçıramaz.
        """
        if not cands:
            self.no_meas_count += 1
            return False
        self.inject(cands)
        lik = np.full(len(self.p), self.cfg.outlier_floor)
        for c in cands:
            s = float(np.clip(c.sigma, self.cfg.min_sigma_m, self.cfg.max_sigma_m))
            d2 = ((self.p[:, 0] - c.north) ** 2 + (self.p[:, 1] - c.east) ** 2)
            lik += c.weight * np.exp(-0.5 * d2 / (s * s))
        self.w = self.w * lik
        tot = self.w.sum()
        if tot <= 0 or not np.isfinite(tot):
            self.w = np.full(len(self.p), 1.0 / len(self.p))
            self.no_meas_count += 1
            return False
        self.w /= tot
        self.no_meas_count = 0
        if self.ess() < self.cfg.ess_frac * len(self.p):
            self.resample()
        return True

    # --- yardımcılar ---
    def ess(self) -> float:
        """Etkin parçacık sayısı — ağırlıkların ne kadar dengeli olduğu."""
        return float(1.0 / np.sum(self.w ** 2))

    def resample(self):
        """Sistematik yeniden örnekleme (çok düşük varyanslı, standart yöntem)."""
        n = len(self.p)
        pos = (self.rng.random() + np.arange(n)) / n
        idx = np.searchsorted(np.cumsum(self.w), pos)
        idx = np.clip(idx, 0, n - 1)
        self.p = self.p[idx]
        self.w = np.full(n, 1.0 / n)

    def estimate(self) -> tuple[float, float]:
        """Ağırlıklı ortalama konum."""
        return (float(np.sum(self.w * self.p[:, 0])),
                float(np.sum(self.w * self.p[:, 1])))

    def spread(self) -> float:
        """Konum belirsizliği: ağırlıklı standart sapmanın büyüklüğü."""
        mn, me = self.estimate()
        vn = float(np.sum(self.w * (self.p[:, 0] - mn) ** 2))
        ve = float(np.sum(self.w * (self.p[:, 1] - me) ** 2))
        return float(np.sqrt(vn + ve))

    def covariance(self) -> np.ndarray:
        """2x2 ağırlıklı kovaryans — belirsizlik elipsi çizmek için."""
        mn, me = self.estimate()
        dn = self.p[:, 0] - mn
        de = self.p[:, 1] - me
        return np.array([
            [np.sum(self.w * dn * dn), np.sum(self.w * dn * de)],
            [np.sum(self.w * dn * de), np.sum(self.w * de * de)]])

    def is_lost(self) -> bool:
        """Süzgeç izi kaybetti mi?"""
        return (self.no_meas_count >= self.cfg.lost_patience
                or self.spread() > self.cfg.lost_spread_m)


def sigma_from_inliers(n_inliers: int, n_ref: int = 300,
                       s_best: float = 4.0, s_worst: float = 25.0) -> float:
    """İç nokta sayısını konum belirsizliğine çevirir.

    Çok iç nokta = güvenilir eşleme = küçük sigma. Bağıntı ölçümle
    kalibre edilir (bkz scripts/07b_sigma_kalibrasyon.py).
    """
    r = float(np.clip(n_inliers / n_ref, 0.0, 1.0))
    return float(s_worst + (s_best - s_worst) * np.sqrt(r))


def weight_from_inliers(n_inliers: int, n_ref: int = 300) -> float:
    """İç nokta sayısını aday ağırlığına çevirir (0-1)."""
    return float(np.clip(n_inliers / n_ref, 0.05, 1.0))

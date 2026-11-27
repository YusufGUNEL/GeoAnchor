"""Regresyon testi: uçuş 03'ün ilk 150 karesinde sıralı füzyon.

Taban (2026-11-27, seed 0): kapsama %100, medyan 7,66 m, %90 13,65 m,
1,58 LoFTR çağrısı/kare. Seed 1: medyan 7,96 m. Eşikler tabanın ~%20 üstünde;
yeniden düzenleme doğruluğu bozarsa test kırılır, tohum farkı kırmaz.

Gerekenler: README "Reproducing" adımları 07'ye kadar koşulmuş olmalı
(önbellek ve results/06*.npz). Yoksa test atlanır. Süre ~2 dk (GPU).
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_07():
    spec = importlib.util.spec_from_file_location("s07", ROOT / "scripts" / "07_sequential.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_sequential_first_150_frames():
    need = [ROOT / "results" / "06_odometry.npz", ROOT / "results" / "06b_odometry_cal.npz"]
    if not all(p.exists() for p in need):
        pytest.skip("önce README'deki hat 06b'ye kadar koşulmalı")
    m = _load_07()
    if not (m.CACHE / "northup_03_640.npy").exists():
        pytest.skip("önbellek yok (03a/03b koşulmamış)")

    tag = "pytest"
    try:
        s, _, _ = m.run(max_frames=150, seed=0, tag=tag, verbose=False)
    finally:
        (ROOT / "results" / f"07_sequential_{tag}.npz").unlink(missing_ok=True)

    assert s["kapsama"] == 1.0
    assert s["medyan_m"] <= 9.0, s
    assert s["p90_m"] <= 16.5, s
    assert s["loftr_per_frame"] <= 1.9, s

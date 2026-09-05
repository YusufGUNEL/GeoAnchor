"""Fetch the Boson-nighttime v1 dataset, resumably.

74 GB arrives as four tar.gz parts that only mean anything concatenated. The
naive route -- `cat part* > whole.tar.gz` then extract -- needs three copies on
disk at once (parts, archive, extracted). Streaming the parts straight into tar
skips the middle copy, which is 74 GB of disk we do not have to find.

Downloads resume: huggingface_hub keeps a cache and re-running picks up where a
dropped connection left off. Safe to kill and restart.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

REPO = "xjh19972/boson-nighttime"
SUBSET = "satellite-thermal-dataset-v1"
HERE = Path(__file__).resolve().parent
RAW = HERE / "veri" / "parcalar"
OUT = HERE / "veri" / "thermal_dataset"


def download() -> Path:
    print(f"-> {REPO}/{SUBSET} indiriliyor (74 GB, devam ettirilebilir)", flush=True)
    path = snapshot_download(
        REPO,
        repo_type="dataset",
        allow_patterns=[f"{SUBSET}/*"],
        local_dir=str(RAW),
        max_workers=4,
    )
    return Path(path) / SUBSET


def extract(parts_dir: Path) -> None:
    parts = sorted(parts_dir.glob("thermal_dataset.tar.gz.part*"))
    if not parts:
        sys.exit(f"parca bulunamadi: {parts_dir}")
    total = sum(p.stat().st_size for p in parts)
    print(f"-> {len(parts)} parca, {total / 1e9:.1f} GB, aciliyor", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)

    # cat parts | tar xz : the concatenated archive never touches disk.
    cat = subprocess.Popen(["cat", *[str(p) for p in parts]], stdout=subprocess.PIPE)
    tar = subprocess.Popen(["tar", "xzf", "-", "-C", str(OUT)], stdin=cat.stdout)
    cat.stdout.close()
    if tar.wait() != 0:
        sys.exit("tar acilirken hata")
    print(f"-> acildi: {OUT}", flush=True)


if __name__ == "__main__":
    parts = download()
    print("-> indirme bitti", flush=True)
    extract(parts)

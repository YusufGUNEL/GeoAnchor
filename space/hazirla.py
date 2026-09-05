"""Rebuild the Space's assets from the repository's own results.

The Space needs a handful of files that already exist elsewhere in the repo --
the per-flight result arrays and the demo video. Copying them in by hand works
once and then rots, and committing a second copy puts 17 MB of duplicated video
in the history. So the folder is generated instead, and `space/assets/` stays
out of git.

    python space/hazirla.py     # then push space/ to the Hugging Face Space
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "space" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

wanted = sorted((ROOT / "results").glob("20_flight_[0-9][0-9].npz")) + [
    ROOT / "results" / "20_multiflight.json",
    ROOT / "results" / "21_flight_difficulty.json",
    ROOT / "figures" / "demo.mp4",
]
for src in wanted:
    if src.exists():
        shutil.copyfile(src, ASSETS / src.name)
        print(f"  {src.name}")
    else:
        print(f"  EKSIK: {src}")
print(f"\n-> {ASSETS}")

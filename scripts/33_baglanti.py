"""Does everything the documents point at still exist?

32_tutarlilik.py checks that the numbers in the documents match the result
files. Nothing checked the other half: a README that names a script, a figure
or a source file it expects the reader to open. Those rot silently and in the
worst way -- someone follows the instructions, hits a missing file, and stops
trusting the rest of the page.

Three classes of reference are checked across every markdown file in the
repository plus the two manuscripts:

  markdown links     [text](path) where path is repo-relative, not http
  image embeds       ![alt](figures/...)
  bare code paths    `scripts/07_sequential.py` and friends inside backticks

Paths that are obviously not files are skipped: URLs, anchors, and the
directories that are gitignored because they are downloaded or generated
(night/veri/, space/assets/, D:\\GeoAnchorData). Those are listed explicitly
rather than guessed at, so a genuinely missing path cannot hide behind a
pattern.

Exit code 1 if anything is missing, so it can gate a commit next to
32_tutarlilik.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]

DOCS = sorted(ROOT.glob("*.md")) + [
    ROOT / "paper" / "README.md",
    ROOT / "paper" / "ARXIV.md",
    ROOT / "paper" / "siu" / "README.md",
    ROOT / "night" / "DURUM.md",
    ROOT / "space" / "README.md",
]

# Referenced on purpose but never committed: downloaded data, generated assets,
# and the external dataset root.
IGNORE_PREFIX = ("http", "#", "mailto:", "D:", "night/veri/", "night/ornekler/",
                 "space/assets/", "results/*", "figures/*", "paper/*",
                 "night/sonuclar/*", "paper/siu/*")

# Named in the documents but supplied by the toolchain, not by this repository.
EXTERNAL = {"IEEEtran.cls"}

MD_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
CODE_PATH = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|tex|json|npz|png|gif|txt|cls|toml|yaml|yml))`")
CODE_DIR = re.compile(r"`((?:src|scripts|night|paper|space|results|figures|data)/)`")


def candidates(text: str) -> set[str]:
    found = set(MD_LINK.findall(text))
    found |= set(CODE_PATH.findall(text))
    found |= set(CODE_DIR.findall(text))
    return found


def resolve(ref: str, doc: Path) -> Path | None:
    """Repo-relative, then document-relative, then by name anywhere in the repo.

    The last case is the common one in prose: the log writes `04_kapi.py` when
    it means night/04_kapi.py. That is a real reference and should be checked,
    but only the basename is given, so it is resolved by search -- and an
    ambiguous basename is treated as found, because the prose is not claiming
    a path in that case.
    """
    ref = ref.split("#", 1)[0]
    if not ref:
        return None
    for base in (ROOT, doc.parent):
        p = (base / ref).resolve()
        try:
            p.relative_to(ROOT)
        except ValueError:
            continue
        if p.exists():
            return p
    if "/" not in ref:
        hits = [h for h in ROOT.rglob(ref)
                if ".git" not in h.parts and "__pycache__" not in h.parts]
        if hits:
            return hits[0]
    return None


def main() -> int:
    missing: list[tuple[Path, str]] = []
    checked = 0
    for doc in DOCS:
        if not doc.exists():
            missing.append((doc, "<belgenin kendisi yok>"))
            continue
        text = doc.read_text(encoding="utf-8")
        for ref in sorted(candidates(text)):
            if ref.startswith(IGNORE_PREFIX) or ref in EXTERNAL:
                continue
            checked += 1
            if resolve(ref, doc) is None:
                missing.append((doc, ref))

    print(f"{len(DOCS)} belge, {checked} yol kontrolu\n")
    if missing:
        for doc, ref in missing:
            print(f"  EKSIK  {doc.relative_to(ROOT)}  ->  {ref}")
        print(f"\n{len(missing)} yol bulunamadi.")
        return 1
    print("Belgelerin isaret ettigi her sey yerinde.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

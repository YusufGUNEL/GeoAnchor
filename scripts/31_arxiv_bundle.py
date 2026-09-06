"""Build the arXiv upload, and refuse to build a broken one.

arXiv compiles the source it is given, on its own TeX Live, in a directory
containing only what the tarball holds. Most failed submissions are one of
three things: a stale .aux left in the archive, a figure referenced but not
included, or an extra top-level directory that breaks every relative path. So
this script does not simply tar the folder -- it checks each of those and
stops rather than producing an archive that will fail on the server.

The manuscript is compiled fresh first: an archive whose source does not build
locally cannot build there either.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"
TEX = PAPER / "geoanchor.tex"
OUT = PAPER / "arxiv-submission.tar.gz"
AUX_SUFFIXES = {".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".synctex.gz",
                ".bbl", ".blg", ".toc", ".nav", ".snm", ".vrb"}


def compile_paper() -> int:
    """Build twice through latexmk and return the page count."""
    if shutil.which("latexmk") is None:
        sys.exit("latexmk yok -- TinyTeX/TeX Live kurulu mu?")
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode",
                        "-halt-on-error", TEX.name],
                       cwd=PAPER, capture_output=True, text=True)
    if r.returncode != 0:
        tail = "\n".join(r.stdout.splitlines()[-25:])
        sys.exit(f"derleme basarisiz:\n{tail}")
    log = (PAPER / "geoanchor.log").read_text(encoding="utf-8", errors="ignore")
    if "There were undefined references" in log:
        sys.exit("cozulmemis referans var -- latexmk'yi tekrar calistir")
    m = re.search(r"Output written on .*?\((\d+) pages", log)
    return int(m.group(1)) if m else 0


def referenced_figures() -> list[Path]:
    """Every \\includegraphics target, resolved against paper/figures/."""
    src = TEX.read_text(encoding="utf-8")
    names = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", src)
    missing, found = [], []
    for n in names:
        p = PAPER / "figures" / n
        (found if p.exists() else missing).append(p)
    if missing:
        sys.exit("makalede olup diskte olmayan sekil(ler): "
                 + ", ".join(p.name for p in missing)
                 + "\nonce: python scripts/30_paper_figures.py")
    return found


def main() -> int:
    pages = compile_paper()
    figs = referenced_figures()

    members = [(TEX, "geoanchor.tex")] + [(f, f"figures/{f.name}") for f in figs]
    for src, _ in members:
        if src.suffix in AUX_SUFFIXES:
            sys.exit(f"yardimci dosya pakete giriyor: {src.name}")

    OUT.unlink(missing_ok=True)
    with tarfile.open(OUT, "w:gz") as tar:
        for src, arcname in members:
            tar.add(src, arcname=arcname)

    with tarfile.open(OUT) as tar:
        names = tar.getnames()
    # Paths must be flat at the root; arXiv does not descend into a wrapper dir.
    assert "geoanchor.tex" in names, names
    size_mb = OUT.stat().st_size / 1e6

    print(f"{OUT.relative_to(ROOT)}  ({size_mb:.1f} MB, {pages} sayfa)")
    for n in names:
        print(f"  {n}")
    if size_mb > 45:
        print("\nUYARI: arXiv siniri 50 MB. fig1'in dpi'sini dusur "
              "(scripts/30_paper_figures.py).")
    print("\nsonraki adim: paper/ARXIV.md icindeki ustveriyi forma gecir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

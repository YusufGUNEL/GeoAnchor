"""One place for figure language, because figures are what people read first.

The English README was showing Turkish figures. Translating them once would fix
today and rot tomorrow, so instead every figure script keeps its strings in a
two-language table and takes the language from the command line:

    python scripts/09_figures.py          # English -> figures/
    python scripts/09_figures.py --tr     # Turkish -> figures/tr/

English is the default because README.md is what GitHub opens. The Turkish set
lands in a subdirectory so the two never overwrite each other, and both come
out of the same code reading the same result files -- a figure cannot disagree
with its translation because there is only one of it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lang() -> str:
    """"tr" if --tr was passed, otherwise "en"."""
    return "tr" if "--tr" in sys.argv else "en"


def figdir() -> Path:
    """Where this run's figures belong, created if missing."""
    d = ROOT / "figures" / "tr" if lang() == "tr" else ROOT / "figures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pick(table: dict[str, dict[str, str]]) -> dict[str, str]:
    """The current language's strings out of a {"en": {...}, "tr": {...}} table."""
    missing = set(table["en"]) ^ set(table["tr"])
    if missing:
        raise KeyError(f"iki dilde ayni anahtarlar olmali; farkli olanlar: {sorted(missing)}")
    return table[lang()]


def pct(value: float, digits: int = 0) -> str:
    """A percentage written the way this language writes it: 93% against %93."""
    s = f"{value:.{digits}f}"
    if lang() == "tr":
        s = s.replace(".", ",")
        return f"%{s}"
    return f"{s}%"


def num(value: float, digits: int = 1) -> str:
    """A number with the language's decimal separator."""
    s = f"{value:.{digits}f}"
    return s.replace(".", ",") if lang() == "tr" else s

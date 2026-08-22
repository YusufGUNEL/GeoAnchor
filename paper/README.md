# Paper

`geoanchor.tex` — IEEE conference format, 4 pages, compiled to `geoanchor.pdf`.

**Title:** *Knowing When You Do Not Know: Sequential Map-Anchored Visual
Localization for GNSS-Denied UAV Flight*

Every number in the paper comes from the JSON files in `../results/` and was
produced by the scripts in `../scripts/`. Nothing was transcribed by hand.

## Building

```bash
pdflatex geoanchor.tex
pdflatex geoanchor.tex      # second pass resolves references
```

Requires `IEEEtran`. On a fresh TinyTeX install:

```bash
tlmgr install ieeetran cite booktabs hyperref xcolor
```

## Venue status

SİU 2026 (July 2026) has passed; SİU 2027 opens for submission around
February. ELECO is biennial and next runs in 2027. An arXiv preprint is
therefore the sensible first step, with the same manuscript going to SİU
afterwards.

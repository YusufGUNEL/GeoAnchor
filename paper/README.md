# Paper

`geoanchor.tex` — IEEE conference format, 5 pages, 3 figures, 2 tables,
compiled to `geoanchor.pdf`.

**Title:** *Knowing When You Do Not Know: Sequential Map-Anchored Visual
Localization for GNSS-Denied UAV Flight*

Every number in the paper comes from the JSON and NPZ files in `../results/`
and was produced by the scripts in `../scripts/`. Nothing was transcribed by
hand.

## Figures

The figures under `../figures/` are labelled in Turkish and sized for the
README, so they cannot go into the manuscript. `figures/` here holds the
manuscript set, rebuilt from the same result files:

```bash
python ../scripts/30_paper_figures.py
```

| | |
|---|---|
| `fig1_trajectory.pdf` | flight 03 over its orthophoto, odometry alone against the fused estimate, both panels in one frame of reference |
| `fig2_cdf.pdf` | error CDF, denominator every frame of the flight |
| `fig3_law.pdf` | match rate against final error over the ten flights |

`fig1` needs the UAV-VisLoc flight 03 folder on disk (`D:\GeoAnchorData\raw`);
the other two build from `../results/` alone, and the script skips `fig1` with
a message rather than failing if the dataset is absent.

## Building

```bash
latexmk -pdf geoanchor.tex
```

Requires `IEEEtran`. On a fresh TinyTeX install:

```bash
tlmgr install ieeetran cite booktabs hyperref xcolor
```

## Submitting

```bash
python ../scripts/31_arxiv_bundle.py
```

Compiles the manuscript, checks that every referenced figure exists, and
writes `arxiv-submission.tar.gz` with a flat layout and no auxiliary files —
the three things that most often break an arXiv upload. Metadata for the
submission form is in `ARXIV.md`.

## Venue status

**arXiv takes this manuscript as it is.** Six pages, English, no length limit
on their side.

**SİU does not, and the earlier plan in this repository was wrong about that.**
The call for papers caps submissions at **four pages** and requires them to be
**in Turkish** unless one of the authors is not a native Turkish speaker, which
does not apply here. So "the same manuscript goes to SİU" was never possible:
SİU needs a separate, Turkish, four-page version.

Cutting six English pages to four Turkish ones is an editorial decision, not a
translation job. The plausible cut is one of the two secondary contributions —
the self-calibration section (III-E and V-C) or the matcher study (VI) — since
each is self-contained and either one alone leaves a coherent paper around the
sequential-fusion result and the deployability predictor.

SİU 2026 (July 2026) has passed; SİU 2027 opens for submission around
February. ELECO is biennial and next runs in 2027.

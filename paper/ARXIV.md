# arXiv submission

Everything below is what the submission form asks for, in the order it asks.
Build the upload with `python ../scripts/31_arxiv_bundle.py`, which writes
`arxiv-submission.tar.gz` next to this file.

## What goes in the tarball

`geoanchor.tex` and `figures/*.pdf`. Nothing else: the bibliography is inline
`\bibitem`, so there is no `.bib` or `.bbl`, and `IEEEtran.cls` ships with
arXiv's TeX Live. Auxiliary files (`.aux`, `.log`, `.fls`, `.fdb_latexmk`,
`.out`) must not be uploaded — arXiv compiles from source and stale aux files
cause failures that are tedious to diagnose.

## Metadata

**Title**

    Knowing When You Do Not Know: Sequential Map-Anchored Visual Localization
    for GNSS-Denied UAV Flight

**Authors**

    Yusuf Günel

**Primary category:** `cs.CV` (Computer Vision and Pattern Recognition)

**Cross-list:** `cs.RO` (Robotics)

`cs.CV` is primary because the contribution is argued against the cross-view
geo-localization literature, which lives there. The result is about a flying
platform, hence the robotics cross-list.

**Comments field**

    5 pages, 3 figures, 2 tables. Code, data preparation and every reported
    measurement: https://github.com/YusufGUNEL/GeoAnchor

**License:** CC BY 4.0. The paper reports on public data (UAV-VisLoc) and the
code is already public; the permissive licence costs nothing and removes a
barrier to citation.

**Abstract** (paste as plain text; arXiv accepts the inline math below)

Matching a downward-looking camera against a pre-loaded satellite map is the
standard route to absolute position when GNSS is denied. The recent literature
optimises this as a single-image retrieval problem, and the common benchmark is
close to saturated. A flying aircraft, however, produces a sequence, and in
that setting the binding constraint is not retrieval accuracy but the fact that
a large fraction of frames cannot be matched at all. We fuse cross-view
matching with visual odometry in a particle filter and evaluate on ten real UAV
survey flights spanning 406-2572 m altitude, 9-103 km per flight and
acquisition dates from 2016 to 2023. On the seven flights whose imagery is
usable against the basemap the system holds a median error of 8.4-24.8 m with
at least 99.7% of frames localised, while visual odometry alone drifts 2803 m
over 74 km. Two by-products follow from the same machinery: the residual
rotation of each map match exposes the platform's heading error, letting the
system calibrate its own magnetometer deviation without GNSS and cutting
odometry drift from 3.795% to 0.865% of distance travelled; and the match rate,
measurable on a planned route before flight, predicts whether the system will
work there at all (rho = -0.764 against log error, with a threshold near 50%).
Finally we report a negative result that we believe generalises: replacing
LoFTR with RoMa raises match rate on the failing flights from 12-42% to 96-100%
and makes end-to-end accuracy dramatically worse, because RoMa returns
confident correspondences for unrelated imagery. For localization, a matcher is
useful in proportion to its ability to stay silent, not to match.

## Before submitting

- [ ] `latexmk -pdf geoanchor.tex` from a clean checkout produces 5 pages with
      no undefined references.
- [ ] The tarball extracts to `geoanchor.tex` + `figures/` at the top level,
      not inside an extra directory.
- [ ] GitHub repository is public and its README matches the paper's numbers.

## After submitting

Put the arXiv ID in the repository README and in `../ILERLEME.md`. The same
manuscript goes to SİU 2027 (submissions open around February); ELECO is
biennial and next runs in 2027.

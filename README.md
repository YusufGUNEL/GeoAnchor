# GeoAnchor — GNSS-Denied Absolute Visual Localization for UAVs

*[Türkçe sürüm için: **[README.tr.md](README.tr.md)**]*

A UAV whose GPS is jammed does not know where it is. Visual odometry gives
relative motion but **drifts** — on this 74 km flight it ends up **2.8 km**
off. Matching the camera against a satellite map gives absolute position but
is **unreliable frame to frame** — on this flight it fails outright on **23%**
of frames (water, uniform farmland, repeating building patterns).

GeoAnchor fuses the two in a particle filter. Neither is sufficient alone;
together they give continuous, drift-free, metre-level positioning with **no
GNSS of any kind**.

![Comparison](figures/10_karsilastirma.png)

---

## Headline result

Real UAV survey flight (UAV-VisLoc, flight 03): **768 frames, 74 km, 77
minutes, 466 m AGL**, over an 8.8 × 7.3 km satellite orthophoto of Taizhou,
China. Ground truth is post-processed GNSS (measured cross-track scatter on
straight legs: **1.5 m**, so the reference itself is clean).

| | Coverage | Median error | p90 | Within 10 m | Match calls / frame |
|---|---|---|---|---|---|
| Visual odometry only | 100% | drifts to **2803 m** | — | 0% | 0 |
| Single-frame map matching | **76.6%** | 5.46 m | 10.71 m | 66.1% | 3.80 |
| **GeoAnchor (fusion)** | **100%** | **6.20 m** | 14.76 m | **76.8%** | **1.52** |

Excluding the four segments where satellite matching collapses entirely
(5.7% of frames — see *Honest limitations*), the fused system holds
**median 5.97 m, p90 11.97 m, 99.9% within 20 m**.

![Error CDF](figures/13_dagilim.png)

The fusion is not only more accurate than either input — it is **2.5×
cheaper** than searching the map every frame, because knowing roughly where
you are turns a global search into a single local check.

---

## Why this is not just "image retrieval on a satellite map"

The published literature on UAV cross-view geo-localization is dominated by
**single-image** retrieval, and the standard benchmark is saturated
(University-1652 sits at 97.5% Recall@1 as of March 2026). But a real UAV does
not take one photograph — it flies a **trajectory**. Almost nothing in the
recent UAV literature exploits that. The one close piece of work,
*BEV-Patch-PF* (Dec 2025), does sequential Bayesian filtering for **ground
vehicles**, not aircraft.

GeoAnchor is built around the sequence:

1. **Visual odometry** supplies the motion model.
2. **Satellite matching** supplies absolute fixes — and is allowed to fail.
3. **A particle filter** carries multiple hypotheses, rejects outlier fixes,
   and coasts through blackouts.
4. **The map calibrates the aircraft's own sensors, online** (see below).

---

## The part I did not expect: the system calibrates its own compass

The homography that aligns a north-up UAV frame to a north-up satellite tile
has a rotation component. If that residual rotation is not zero, the
**heading angle itself is wrong by exactly that much**.

Measuring it across the flight showed the heading error depends on which way
the aircraft is pointing — **−1.93°** on the northwest legs, **−7.08°** on the
southeast legs. That direction-dependent signature is the classic fingerprint
of magnetometer hard-iron error, the thing aircraft fix with a "compass swing".

Cross-checking against ground truth confirmed it: the odometry direction bias
computed from GNSS was **+1.65°** and **+7.22°** — same magnitudes, opposite
sign, exactly as the geometry predicts.

| | Measured from the map (no GNSS) | Computed from ground truth |
|---|---|---|
| Northwest legs | −1.93° (σ 0.86) | +1.65° |
| Southeast legs | −7.08° (σ 1.73) | +7.22° |

So the aircraft can measure and correct its own compass deviation against the
map, with no GNSS at all. Feeding this back into the odometry cut its drift
from **3.795%** to **0.865%** of distance travelled — 2803 m → 639 m over
74 km. The same trick recovers scale (terrain elevation changes the true
ground sampling distance) from the homography's scale component.

---

## Two other things the data was hiding

**The dataset's own metadata is wrong in two places.** Both were found by
measurement, not by reading the documentation.

1. *The attitude channels are swapped.* The dataset states "Omega = pitch,
   Kappa = roll". Regressing the localization error in the body frame gives
   along-track ~ Kappa with coefficient **+0.981** (R² 0.677) and cross-track
   ~ Omega with coefficient **−0.972** (R² 0.765). Coefficients landing on ±1
   mean the physics (ground offset = altitude × tan θ) is exactly right and
   only the labels are reversed.

2. *Phi1, not Phi2, is the camera heading.* Phi2 matches the flight's ground
   course to a median of 0.00°, which looks convincing — but LoFTR matching
   against the satellite leaves ~0° residual with Phi1 and ~12° with Phi2. The
   12° gap is the wind crab angle: Phi1 is where the nose points, Phi2 is
   where the aircraft actually goes.

**The camera is mounted 2° nose-down.** At 466 m altitude, a 2° tilt puts the
image centre **16 m** ahead of the aircraft on the ground. This was the single
largest error source. Calibrating it on the first 20% of the flight and
evaluating on the remaining 80%:

| | Before | After |
|---|---|---|
| Median error | 16.82 m | **6.12 m** |
| Within 5 m | 2.6% | **40.0%** |
| Within 10 m | 17.4% | **80.9%** |

---

## How it works

```
UAV frame ──rotate by −heading, scale by altitude──► north-up, metric crop
                                                          │
                    ┌─────────────────────────────────────┤
                    ▼                                     ▼
        DINOv2 global descriptor                 LoFTR dense matching
        (2709 satellite tiles indexed)           against a 400 m crop
                    │                                     │
                    │ candidate regions                   │ homography
                    ▼                                     ▼
              ┌───────────────────────────────────────────────┐
              │  attitude correction: image centre → aircraft  │
              │  online calibration: compass bias, scale       │
              └───────────────────────────────────────────────┘
                                    │
   visual odometry ────────────────►│ PARTICLE FILTER ──► position + uncertainty
   (SIFT, consecutive frames)       │  motion + multi-hypothesis measurement
                                    └───────────────────────────────────────
```

**Why a particle filter and not a Kalman filter.** Satellite-matching error is
not Gaussian. Most of the time it is right to a few metres; occasionally it
confidently points at a completely different place (a similar field, the same
building pattern one block over). That distribution is multi-modal and
heavy-tailed. A Kalman filter assumes a single Gaussian mode and one such
outlier drags it permanently off. The particle filter keeps several hypotheses
alive and decides over time which one is consistent with the flight, and a
flat outlier floor in the likelihood stops any single bad fix from wiping out
the belief.

**Why LoFTR and not SIFT for map matching.** The satellite imagery is from a
different season than the flight — autumn golden fields against dark green
ones, different sun angle, buildings that were not there yet. Measured on the
same four frames: SIFT yielded 12/4/24/7 inliers; LoFTR yielded
**104/21/280/140**. Detector-free dense matching survives the appearance gap;
classical keypoints do not. (SIFT *is* used for odometry between consecutive
UAV frames, where no appearance gap exists — it is faster and runs on the CPU,
leaving the GPU to the map matching.)

---

## Honest limitations

Written down first, so nothing here is oversold.

- **Satellite matching collapses over featureless terrain.** Four segments
  (5.7% of frames, longest 21 frames ≈ 2 km of flight) produced zero inliers.
  There the filter coasts on odometry and degrades to a maximum of 338 m
  before re-anchoring. This is real and visible as red dots in the figure — it
  is not smoothed away.
- **Processed offline**, not on the aircraft in flight. Throughput is 866 ms
  per frame on a laptop RTX 3050 Ti; frames arrive every 7 s in this dataset,
  so it is comfortably real-time *for this flight*, but it has not been run on
  embedded hardware.
- **Attitude and altitude are assumed available** from the IMU and a
  barometric/radar altimeter. Neither depends on GNSS, and this matches the
  pose-prior protocol used by the AnyVisLoc benchmark — but it is an
  assumption, and the compass bias result above shows those sensors are not
  perfect either.
- **The boresight calibration uses the first 20% of the flight.** Real systems
  do this once at installation; here it is done from data, and everything
  reported is evaluated on the held-out remainder.
- **One flight, one region, one season.** Taizhou is flat river delta. Nothing
  here demonstrates behaviour over mountains, at night, or in winter.
- **The compass deviation curve is fitted at only two headings**, because the
  survey pattern only flies two. The physical model (hard-iron error) predicts
  a sinusoid in heading, but this flight cannot identify it — with two
  headings it is effectively a two-point lookup.
- **Planar homography assumption.** Valid for near-nadir frames (pitch and
  roll stay within ±5° here); it degrades for oblique views. Building relief
  displacement is the main residual error source and is why ~6 m, not ~1 m, is
  the floor.

---

## Reproducing

```bash
pip install torch torchvision timm kornia opencv-python rasterio gdown \
            numpy pandas matplotlib imageio

# 1. data (2.04 GB sample of UAV-VisLoc, flight 03)
python -m gdown "https://drive.google.com/uc?id=16tY7tPZiNIoyAhknvyXnp0jAfccIcHtL"

python scripts/00_inspect.py          # verify geo-referencing, estimate GSD
python scripts/01b_convention.py      # determine yaw convention empirically
python scripts/02_build_tiledb.py     # DINOv2 descriptors for 2709 tiles
python scripts/03a_cache_northup.py   # cache north-up UAV crops
python scripts/03b_cache_tiles.py
python scripts/03c_retrieval_sweep.py # retrieval quality sweep
python scripts/04f_oracle2.py         # matching accuracy ceiling
python scripts/05_single_frame.py     # PHASE 1 baseline
python scripts/06_odometry.py         # PHASE 2 odometry + drift
python scripts/06c_yaw_from_map.py    # compass bias measured from the map
python scripts/07_sequential.py       # PHASE 3 fusion  ← main result
python scripts/08_robustness.py       # PHASE 4 degradation + outage
python scripts/11_ablation.py         # PHASE 5 ablation
python scripts/09_figures.py          # figures
python scripts/10_demo_video.py       # demo video
```

Hardware used: Windows 11 laptop, **NVIDIA RTX 3050 Ti, 4 GB VRAM**. Peak
usage 1.4 GB — nothing here needs a datacentre GPU.

## Layout

```
src/geo.py              geo-referencing, windowed GeoTIFF access, metric crops
src/flight.py           flight sequence loading
src/features.py         DINOv2 global descriptors (CLS + GeM)
src/tiles.py            satellite tile grid and descriptor database
src/matching.py         LoFTR wrapper + RANSAC similarity
src/geometry.py         attitude-induced offset model, boresight calibration
src/localize.py         single-frame localization (retrieval → verify → correct)
src/odometry.py         visual odometry between consecutive frames
src/particle_filter.py  particle filter with measurement-driven injection
src/sequential.py       the fused sequential system + online calibration
src/degrade.py          six realistic image degradations
```

`ILERLEME.md` is the full working log — every measurement, every dead end,
every bug found and what it cost. Written as the work happened, in Turkish.

## Data

UAV-VisLoc (Xu et al., 2024, arXiv:2405.11936) — flight 03, released for
non-commercial research. Satellite basemap ships with the dataset.

## Licence

MIT for the code. The dataset keeps its own terms.

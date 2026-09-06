---
title: GeoAnchor — GNSS-Denied UAV Localization
emoji: 🛰️
colorFrom: blue
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
license: mit
short_description: A UAV finds itself on a satellite map with no GPS. Ten real flights, 8-25 m median error, and the same law at night.
---

Interactive walkthrough of the [GeoAnchor](https://github.com/YusufGUNEL/GeoAnchor)
results: visual odometry fused with satellite-map matching in a particle filter,
evaluated on ten real UAV survey flights — plus what happens when the same
system is pointed at a thermal camera at night.

Everything shown is precomputed, so the Space runs on free CPU hardware. The
models and the full pipeline are in the repository.

Assets are generated, not committed: run `python space/hazirla.py` from the
repository root before pushing, which copies the result arrays and distils
`night/sonuclar/` into the one summary the night charts read.

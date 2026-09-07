---
title: GeoAnchor — GNSS-Denied UAV Localization
emoji: 🛰️
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: mit
short_description: A UAV finds itself on a satellite map, no GPS
---

Interactive walkthrough of the [GeoAnchor](https://github.com/YusufGUNEL/GeoAnchor)
results: visual odometry fused with satellite-map matching in a particle filter,
evaluated on ten real UAV survey flights — plus what happens when the same
system is pointed at a thermal camera at night.

**Static, not Gradio.** Every number shown was computed offline and committed to
the repository, so the page needs no server: it fetches one JSON and draws the
charts with Plotly. Hugging Face now bills Gradio Spaces even on free CPU, and
this app never needed a running process anyway — static is both free and
faster, with none of the cold starts a sleeping Space has.

Assets are generated, not committed:

```bash
python space/hazirla.py     # distil results/ and night/sonuclar/ into assets/
python space/dagit.py       # create the Space and upload
```

`hazirla.py` turns the per-flight NPZ arrays into one `data.json` — thinned to
every second frame, with NaN written as null so a frame that produced no fix
draws as a gap — and copies the two media files the page embeds. `dagit.py`
refuses to upload if those assets are missing.

To look at it before publishing:

```bash
python -m http.server 7862 --directory space
# then open http://127.0.0.1:7862/index.html
```

`app.py` is the previous Gradio version, kept because it runs locally with one
command and is the easier thing to modify.

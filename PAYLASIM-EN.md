# Sharing drafts — English channels

`PAYLASIM.md` covers LinkedIn in Turkish. This file covers the places that
actually produce stars and inbound messages: Reddit, Hacker News, X, and the
indexes. Read each one before posting and change the wording to sound like you.

There is a second story now, and on the technical channels it is the stronger
one: the same project was pointed at a thermal camera at night, the daylight
matcher scored a flat zero, and the property that predicts where the system
works turned out to hold there too — measurable from the satellite map alone,
before any matching. Lead with that on r/computervision and Hacker News if you
want the comments to be about the finding rather than about the demo.

Two rules that decide whether these land:

1. **Lead with the failure, not the result.** "I got 15 m error" is a claim
   nobody can check. "Odometry ended up 2.8 km off and map matching failed on a
   quarter of the frames, so I fused them" is a story an engineer recognises.
2. **Never post a link with no body.** On Reddit and HN a bare link reads as
   promotion and gets downvoted or removed. Say what it is, what is measured,
   and what does not work.

Post the Space link, not just the repo — a page people can click through beats
a page they have to clone: https://huggingface.co/spaces/MANOROMAN/GeoAnchor

---

## r/computervision

**Title**

> GNSS-denied UAV localization: fusing visual odometry with satellite-map matching, evaluated on 10 real flights (406–2572 m)

**Body**

> A UAV with jammed GPS has two visual options and neither survives alone.
>
> Visual odometry always produces an answer but drifts — on a 74 km flight in
> this dataset it ends up 2.8 km off. Matching the down-facing camera against a
> pre-downloaded satellite map does not drift, but it fails outright on ~23% of
> frames: water, uniform farmland, repeating rooftop patterns.
>
> I fused the two in a particle filter (DINOv2 for retrieval, LoFTR for the
> pose, VO for the motion model) and ran it over ten real survey flights from
> UAV-VisLoc — 406 to 2572 m altitude, 9 to 103 km per flight, acquisition
> dates from 2016 to 2023. Ground truth is post-processed GNSS.
>
> Seven flights: median error 8–25 m, position on ≥99.7% of frames. Three
> flights: it collapses, 53 m to 648 m median.
>
> The part I found more interesting than the median: **a single measurable
> property predicts which group a flight falls into, and it is not altitude.**
> The 2572 m flight works; a 551 m one does not. What separates them is the
> match rate — the fraction of frames that match the map when the true position
> is already known. Above 50% the filter holds, below it collapses, correlation
> between match rate and log error is −0.764. Since that quantity is measured
> against the satellite map, it can be computed for a planned route *before the
> aircraft takes off*.
>
> Three things I had to find the hard way and none of them were documented:
> the camera was mounted 2° nose-down (16 m of ground offset at 466 m and the
> single largest error source), the aircraft's compass bias varied with heading
> (the system now calibrates its own heading from the map, with no GNSS), and
> the dataset's own documentation has two errors in the attitude columns.
>
> Runs in 1.4 GB of VRAM. The three failing flights and the vibration breakdown
> are in the repo — I would rather show them than trim the table.
>
> Interactive results (pick a flight, see the error curve and where matching
> collapses): https://huggingface.co/spaces/MANOROMAN/GeoAnchor
> Code and write-up: https://github.com/YusufGUNEL/GeoAnchor
>
> Happy to be told what I got wrong — particularly on the particle filter's
> resampling, which I suspect is cruder than it needs to be.

**Also worth posting to:** r/drones (rewrite the opening for pilots, not CV
people), r/Robotics, r/remotesensing.

---

## Hacker News

**Title**

> Show HN: GeoAnchor – a UAV that locates itself on a satellite map with no GPS

**Body (first comment, post it yourself right after submitting)**

> Author here. This started as a question I could not answer: if GPS is jammed,
> can a drone still know where it is using only a camera and a map it downloaded
> before takeoff?
>
> Visual odometry drifts (2.8 km off after 74 km). Satellite-map matching does
> not drift but fails on about a quarter of frames — water, farmland, repeated
> rooftops. Fusing them in a particle filter gives 8–25 m median error on seven
> of ten real survey flights, with a position on essentially every frame, in
> 1.4 GB of VRAM.
>
> The finding I did not expect is that flight-level success is predictable in
> advance from a property of the terrain rather than of the algorithm, so a
> route can be screened before anyone flies it. Three flights fail and they are
> in the repo with the diagnosis.
>
> Evaluated on UAV-VisLoc, ground truth is post-processed GNSS, calibration on
> the first 20% of each flight and evaluation on the remaining 80%.

HN dislikes marketing language. No emoji, no "excited to share", no adjectives
about your own work. State the problem, the number, the limitation.

---

## X / Bluesky thread

> 1/ A drone whose GPS is jammed does not know where it is.
>
> I gave one a downward camera and a satellite map downloaded before takeoff.
> Over ten real flights it finds itself to 8–25 metres, with no GNSS of any
> kind, in 1.4 GB of VRAM. 🧵

> 2/ Two methods, both insufficient.
>
> Visual odometry never stops answering but drifts: 2.8 km off after 74 km.
> Satellite matching never drifts but fails on 23% of frames — water, farmland,
> repeating rooftops.
>
> A particle filter uses each to cover the other's failure.

> 3/ The part I did not expect.
>
> Which flights work is predictable, and altitude is not the predictor — the
> 2572 m flight works, a 551 m one collapses.
>
> It is the match rate against the map. Above 50% it holds, below it breaks.
> Correlation −0.764.

> 4/ That number is measurable on a planned route *before takeoff*. So the
> system can say "I will not work here" instead of failing in flight.
>
> Three flights fail and are in the repo, with the diagnosis rather than a
> trimmed table.
>
> Interactive: https://huggingface.co/spaces/MANOROMAN/GeoAnchor
> Code: https://github.com/YusufGUNEL/GeoAnchor

---

## LinkedIn — short English version

For international recruiters. Keep the Turkish post for the local network; do
not post both on the same day.

> A UAV with jammed GPS does not know where it is. I gave one a downward-facing
> camera and a satellite map downloaded before takeoff.
>
> Visual odometry drifts — 2.8 km off after a 74 km flight. Matching the camera
> to the map does not drift but fails on a quarter of frames. Fused in a
> particle filter, they cover each other: 8–25 m median error across seven of
> ten real survey flights (406–2572 m altitude, 9–103 km each), position on
> ≥99.7% of frames, 1.4 GB of VRAM.
>
> What I find more useful than the median is that success is predictable from
> the terrain before flying, so a route can be screened in advance. The three
> flights where it fails are published with the diagnosis.
>
> Interactive results: https://huggingface.co/spaces/MANOROMAN/GeoAnchor
> Code: https://github.com/YusufGUNEL/GeoAnchor

---

## Indexes and the preprint

- **Hugging Face Space** — live at https://huggingface.co/spaces/MANOROMAN/GeoAnchor.
  It is a *static* Space: Hugging Face bills Gradio even on free CPU, and the
  page never needed a running process, so it ships as HTML plus one JSON.
  Rebuild and push it with:

  ```bash
  python space/hazirla.py            # build assets from results/ and night/
  python space/dagit.py --kuru-calisma   # check what would be uploaded
  python space/dagit.py              # create the Space and push
  ```

  `dagit.py` refuses to upload without the assets, because a Space that starts
  and then throws on its first read is worse than no Space, and it checks the
  token's permissions before touching the network. Uploading needs a token with
  `repo.write` from huggingface.co/settings/tokens, then `hf auth login`.
- **arXiv** — the manuscript is finished and the upload is built by
  `python scripts/31_arxiv_bundle.py`; the submission form's metadata is in
  `paper/ARXIV.md`. Category cs.CV, cross-list cs.RO. A first submission to
  cs.CV needs an endorsement from someone who has published there; ask a
  supervisor or a co-author. Without one the fallback is a technical report on
  Zenodo, which gives a DOI and is citable.
- **SİU is a separate manuscript, not this one.** Its call caps papers at four
  pages and requires Turkish. See the venue note in `paper/README.md`.
- **Papers with Code** — add the repo against the "Visual Localization" and
  "Image Retrieval" tasks. Free, indexed by Google, and it is where people
  looking for a baseline actually search.
- **GitHub hygiene** — the repository description and topics are already set.
  Add the Space link to the About panel, and put the demo GIF in the first
  screen of the README (it is currently below the fold on mobile).

## Order and timing

Do not fire everything at once. One channel per day, so you can answer comments
properly on each:

1. Space goes live, README links to it.
2. r/computervision (weekday morning, US time).
3. Hacker News (Tuesday–Thursday, around 09:00 US Eastern).
4. LinkedIn Turkish, then the English version three days later.
5. X thread on the same day as LinkedIn.
6. Papers with Code and the preprint whenever they are ready.

The single most valuable thing you can do is answer every technical comment
within a few hours. That is what turns a post into an audience.

# Sharing — Reddit, and where the work is indexed

`PAYLASIM.md` has the LinkedIn post, in Turkish, and it is the one that matters
for a Turkish network. This file has the one English channel worth the effort
plus the places the work should be listed.

**What was cut, and why.** Hacker News is a lottery: front page or nobody, and
a flop is a bad first experience for no gain. An X or Bluesky thread needs an
audience you already have. A second, English LinkedIn post splits one network
in half — the international reader gets the README, the Space and the paper,
all of which are already in English.

Read the draft before posting and change the wording to sound like you.

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

**If it goes well:** r/drones (rewrite the opening for pilots rather than CV
people), r/Robotics, r/remotesensing. One at a time, days apart — the point of
posting is answering the replies, and you cannot do that in four places at
once.

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
- **GitHub** — description, topics and the About panel's website link are set;
  the website points at the Space.

## Order and timing

Two posts, days apart:

1. **LinkedIn, Turkish** (`PAYLASIM.md`) — weekday morning. Your own network,
   the one that leads to conversations.
2. **r/computervision** — a few days later, weekday morning US time. Different
   audience, so no repetition problem.

Then Papers with Code and the preprint whenever they are ready.

The single most valuable thing you can do is answer every technical comment
within a few hours. That is what turns a post into an audience — and it is the
reason for not posting everywhere on the same day.

# Big host -> small guest: forward subscriber test, plan fixed before any data (9 Nov 2026, ~21:45 IST)

Agreed with Shimona on 9 Nov 2026. Written before any video published on or after 10 Nov 2026 existed. Adds to, and
does not replace, COLLAB_SPILLOVER_PLAN_7NOV.md (its result is reported on its own). Every earlier result stands.

## Why
Spillover should be largest when a BIG channel puts a SMALL creator in front of its audience: a small share of the
host's audience is a large jump for the guest. Koch et al. (2018) found collaboration gains mostly for channels under
100k. Our past-data tests pooled equal-sized pairs, where little is expected.

## Events (identity rules only)
- A video published from 10 Nov 2026 00:00 IST (9 Nov 18:30 UTC) to 30 Nov 2026 by ANY held YouTube channel A (any
  category: podcasts and media count as hosts) that features a held in-scope creator B != A:
  (a) B's @handle in the title or description, or
  (b) the joint-video title rule of JOINT_VIDEO_SPILLOVER_PLAN_9NOV.md (marker + B's name).
- Big host: A's subscribers >= 3 x B's subscribers (latest reading before the video). Primary.
- Only the first event per B within 7 days (several hosts on the same days are one event, timed by the first).

## Measure
growth_after = log(subs(t+48h) / subs(t)), growth_before = log(subs(t) / subs(t-48h)); subs = the nearest YouTube
subscriber reading (profile_snapshots) within 3 hours of each time. Effect per event = growth_after - growth_before.
Placebo: the same difference at 200 random times per B (seed 0) between 7 Nov and the last reading minus 48 h, with no
event of B within 7 days.

## Test and pass mark
- Primary (host >= 3x): mean effect, 95% interval from a bootstrap resampling B creators (2,000 draws, seed 0).
  DETECTED only if the interval is above 0 AND the placebo interval includes 0.
- Secondary (reported, same rule): host >= 10x.
- Run once, on 20 Nov 2026 (the thesis cut-off), with whatever events have both readings; fewer than 20 counted
  events: printed as early evidence, not a result. If the data keeps coming, a second, final run on 30 Nov is reported
  next to it (both runs listed).

## Data this needs (and the fix made with this plan)
Subscriber readings at least every ~3 hours for every held channel: added .github/workflows/snapshot_subscribers.yml
(every 30 minutes, ~8 quota units a run) because GitHub started the 2-hourly job only every 5-7 hours on 7-9 Nov.
New host videos come from the 2-hourly upload discovery (snapshot_youtube.py, all held channels).

## Exploratory, past data (labelled exploratory, NOT confirmatory)
The 52 joint videos of 2024-2026 (models/joint_video_events_9nov.json) with host >= 10x guest, analysed with the
joint-video measure (guest's views 14 days after vs 30 before). These videos were already analysed as part of the
pooled joint-video test, so this subgroup cannot confirm anything; it is shown only as context.

## Not allowed
Changing the rules, the ratio or the windows after seeing data; running repeatedly until something passes.

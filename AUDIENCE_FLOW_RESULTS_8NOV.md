# Collaboration spillover on past data: results (8 Nov 2026)

Plan: AUDIENCE_FLOW_PLAN_8NOV.md (fixed before any number). Script: scripts/audience_flow_test.py run (one run).
Output: models/audience_flow_results_8nov.json. Events: 159 tags (A's post @mentions held in-scope creator B,
last 365 days, first tag of B by A within 30 days). Comments: 59,770 around the tags and 101,783 for the placebo
times (scripts/ingestion/youtube_comments_backfill.py --video-ids-file, top 100 per video by relevance).

## Test 1 (primary): audience flow
Effect per event = share of B's commenters (30 days after) who commented on A in the 60 days before the tag, minus
the same share for the 30 days before.
- Events counted (B with >= 20 commenters each side): 100, from 70 creator pairs.
- Mean effect **-0.0017 (-0.17 percentage points), 95% CI [-0.0045, +0.0006]** (bootstrap over pairs).
- Placebo (5 random no-tag times per event, 431 counted): -0.0032, CI [-0.0057, -0.0011].
- **Verdict: NOT detected.** The interval includes 0. The placebo is itself slightly negative: the overlap between
  two audiences drifts down over time, at tags and at random times alike. (The difference event minus placebo,
  about +0.15 points, is not part of the pre-set test and is not claimed.)

## Test 2 (secondary): B's engagement in the 7 days after the tag
- Events counted: 116, from 80 pairs. Mean +0.040 (about +4%), 95% CI [-0.086, +0.152].
- Placebo (516 counted): +0.029, CI [-0.056, +0.127].
- **Verdict: NOT detected.**

## Reading
Being tagged by another fitness/health creator did not move the tagger's commenters onto the tagged creator's videos,
and did not lift the tagged creator's engagement in the following week, beyond what random dates show. Together with
the sponsorship test (SPILLOVER_RESULTS_7NOV.md: 298 cases, boosts above about +2% ruled out) the evidence points to
no detectable spillover among these Indian fitness and health creators. Still to come: the replication on 2 years of
tags with up to 300 comments per video (pre-registered in the plan), and the forward subscriber study
(COLLAB_SPILLOVER_PLAN_7NOV.md, around 21 Nov).

Limits: top 100 comments per video, not all; commenter names can change; a tag is not always a joint video; YouTube only.

## "Came from A" comments (plan: MENTION_SPILLOVER_PLAN_8NOV.md; models/mention_spillover_results_8nov.json)
- 100 events (63 pairs) with >= 50 of B's comments on each side. Comments naming A per 1,000 of B's comments, after
  minus before: **-0.48, 95% CI [-1.40, +0.19]**; placebo +0.34 [-0.10, +0.93]. **Verdict: NOT detected.**
- Single cases exist: 3 events have comments naming A after the tag and none before, e.g. "Inspired from notsofit" on
  Prem Joshi's video after NotSoFit (Yatharth) tagged him (June 2026). Spillover happens for individual viewers but
  is too rare to move the averages.

## Cross-platform sponsorship spillover, same creator (plan: CROSS_PLATFORM_SPILLOVER_PLAN_8NOV.md;
## models/cross_platform_spillover_results_8nov.json)
- 34 counted events from 23 creators (sponsored fitness post on one platform; the same creator's non-sponsored posts on
  the other platform, 7 days after vs 30 days before, against the creator's own median).
- Effect **+0.009 (about +1%), 95% CI [-0.25, +0.26]**; placebo +0.003 [-0.10, +0.13]. **Verdict: NOT detected.**
- YouTube -> Instagram: -0.09 [-0.59, +0.41] (11 events); Instagram -> YouTube: +0.06 [-0.23, +0.32] (23 events).
- Too few Instagram posts around YouTube sponsorships: the interval is too wide to rule much out. To repeat once the
  Instagram collection of the 158 in-scope creators (instagram_daily.py scope_targets, from 9 Nov) has run.

## Brand-awareness spillover through the creator network (plan: BRAND_SPILLOVER_PLAN_8NOV.md;
## models/brand_spillover_results_8nov.json; run once on 9 Nov 2026)
- 6,555 events (278 linked pairs, 48 fitness brands): A's fitness sponsored post for brand X, linked creator B never
  sponsored by X within 60 days. Comments on B's top 5 videos, 30 days before vs after: ~570,000 comments fetched
  for this test on 8-9 Nov (15,505 videos; the ~700 left have no comments).
- 3,985 events (188 pairs) had >= 50 comments on each side. Comments naming brand X per 1,000 of B's comments, after
  minus before: **+0.09, 95% CI [-0.12, +0.41]**. Placebo (same B and brand, 5 random times each; 14,461 counted):
  **-0.31 [-0.71, -0.02]**. **Verdict: NOT detected** (the event interval includes 0, and the placebo interval does not).
- The placebo excluding 0 means brand mentions on B's channel drift downward at random times. The events sit
  +0.40 above the placebo, but a comparison against the placebo was not the pre-registered test, so it is only a lead:
  it would need its own plan, written before data, on new events (e.g. sponsored posts from 10 Nov on).
- Speed change made before the run, not after: top_videos now reads all videos in one query (same rule: top 5 by
  comment count, nulls last; ties by video id) because one query per window meant ~57,000 round trips.

## Event study re-run on more data (scripts/run_spillover_event_study.py, unchanged code; models/spillover_event_study_9nov.json, 9 Nov 2026)
Same test as 31 Oct (models/spillover_event_study.json kept): after A's sponsored YouTube video, extra views / comments on
linked B's older videos in 12-hour windows up to 48 h, placebo keeps the hour of day, Bonferroni over 4 windows.
- 2-hourly readings (now 4 weeks): 63 sponsored events, 19 (event, B) pairs (was 6). Smallest p after the event 0.20 -> **not detected**.
- Comments (history): 594 pairs from 41 B creators (was 108 from 21). Smallest p 0.14 -> **not detected**; without B's
  own upload nearby 212 pairs, p 0.19; random unlinked pairs (false-alarm check) clean, p 0.34.
- The "direct" check (A's own older videos) is also not detected, so this method shows no positive control: it cannot
  see even the sponsoring creator's own short-term lift, which limits what its null result says.

## Joint-video spillover (plan: JOINT_VIDEO_SPILLOVER_PLAN_9NOV.md; models/joint_video_results_9nov.json; run once on 9 Nov 2026)
- 240 joint videos in 730 days (A's title names B with "ft / with / x / & ..." or B's @handle); a random sample of 30
  titles checked by eye before the run: about 25 real joint videos, the rest league posts about teams or a mention.
- Primary, all B: 177 counted events (135 pairs). B's own videos 14 days after vs 30 days before, against B's median:
  **+0.033 (about +3%), 95% CI [-0.07, +0.13]**; placebo -0.01 [-0.06, +0.04] (clean). **Verdict: NOT detected.**
  A lift above about +14% is ruled out.
- Secondary, B under 100k subscribers: 28 events, -0.09 [-0.59, +0.29]; placebo +0.08 [-0.12, +0.25]. NOT detected.
- Host A (printed only): -0.04 [-0.13, +0.05].
- Reading: even direct joint videos, the strongest link we can build, do not lift the partner's next videos among these
  Indian fitness/health creators. The placebo is clean here, so this is the cleanest null of all the tests.

## Sponsorship spillover onto the creator's own other videos (plan: SPONSOR_CARRYOVER_PLAN_9NOV.md;
## models/sponsor_carryover_results_9nov.json; run once on 9 Nov 2026)
- 1,026 events (A's fitness sponsored video, first per brand within 60 days); 431 counted (59 creators) with >= 50
  held comments on A's own non-sponsored videos on each side.
- Comments naming the brand per 1,000, 30 days after minus before: **-0.01, 95% CI [-1.20, +0.88]**; placebo -0.08
  [-1.56, +1.47]. **Verdict: NOT detected.** Viewers do not talk about the sponsor more on the creator's next videos.

## Big host -> small guest (plan: BIG_HOST_SPILLOVER_PLAN_9NOV.md, 9 Nov 2026)
- FORWARD test (confirmatory): events from 10 Nov; guest's subscribers 48 h after vs before; runs on 20 Nov 2026
  (`python scripts/big_host_forward_test.py run`), final run 30 Nov. Track the count with `... count` (no outcome).
- EXPLORATORY past data (context only, NOT a result: these videos were already in the pooled joint-video test):
  52 joint videos with host >= 10x guest, 29 counted: guest's views +0.01, 95% CI [-0.23, +0.29]. Nothing visible.
- Data gap found and fixed: GitHub started the 2-hourly timer only every 5-7 h on 7-9 Nov (none for 9 h on 9 Nov);
  `.github/workflows/snapshot_subscribers.yml` (subscribers only, every 30 min, ~8 units) must be pushed to main.

## Cross-promotion mechanism for the detected cross-platform link (plan: CROSS_PROMOTION_MECHANISM_PLAN_10NOV.md;
## models/cross_promotion_mechanism_10nov.json; run once on 10 Nov 2026)
- Update of the DETECTED test on 10 Nov data (unchanged code, now 105 creators, was 90): Instagram posts -> comments on
  the same creator's YouTube videos older than 72 h F 1.559 (placebo median 1.016), p 0.002; YouTube comments ->
  Instagram posts F 1.561, p 0.014. The cross-platform temporal link stays detected on more creators.
- Primary (Instagram captions mentioning YouTube, median split): only 13 creators ever mention YouTube in captions
  (median share 0): fewer than 15 in a group, printed, not a result.
- Secondary (YouTube texts mentioning Instagram, 52 vs 53 creators, YouTube comments -> Instagram posts): F difference
  -1.01, relabelling p 0.98: NOT supported. The link is, if anything, stronger for creators who do NOT mention Instagram
  (F 2.08, p 0.014) than for those who do (F 1.07, p 0.33).
- Reading: the detected link is not explained by explicit cross-promotion in captions or descriptions. It is consistent
  with audiences following creators across platforms on their own, but equally with a shared rhythm (busy weeks on both
  platforms); Granger remains prediction, not cause.

## Between-creator Granger (plan: BETWEEN_CREATOR_GRANGER_PLAN_10NOV.md, pushed 7c1402c before running;
## models/between_creator_granger_10nov.json; run once on 10 Nov 2026)
Same method as the detected within-creator test, between creators: does A's posting (YouTube + Instagram per day) predict
comments on linked B's videos older than 72 h, lags 1-3, 365 days? Needs BOTH placebos below 0.05.
- PRIMARY, tag pairs: 238 of 257 pairs used. F 1.317; timing placebo median 1.095, **p 0.002**; unlinked placebo (same B,
  random never-linked A') median 1.179, **p 0.054**. **Verdict: NOT detected** (misses the second check narrowly).
- SECONDARY, joint-video pairs: 164 of 185 used. F 1.274; timing p 0.034; unlinked p 0.124. **NOT detected.**
- Reading: linked creators' timing does predict B's old-video comments better than shuffled timing, but most of that is
  shared calendar rhythm (unlinked pairs also score above the shifted placebo: 1.18 vs 1.10). What is left that is specific
  to linked pairs is suggestive (p 0.054) but not established. Not re-run; not to be re-run to cross 0.05.

## Replication (plan section "Replication": 730 days, up to 300 comments per video; run ONCE on 12 Nov 2026 evening,
## after the comment fetch reached 99.8% of the videos that have comments; models/audience_flow_results_rep_9nov.json)
441 events. Same code, rules and pass mark as the first run.
- Test 1 (primary, audience flow): 246 events counted (160 pairs). Mean -0.0006, 95% CI [-0.0023, +0.0013];
  placebo (934) -0.0022, CI [-0.0052, -0.0001]. **Verdict: NOT detected.**
- Test 2 (secondary, B's engagement in the 7 days after A tags B): 291 events counted (173 pairs). Mean **+0.095**
  (about +10% views+likes against B's own usual), 95% CI **[+0.005, +0.185]**; placebo (1,165 counted) -0.010,
  CI [-0.056, +0.038] includes 0. **Verdict: DETECTED.**
- Reading: on the larger replication, a creator's videos in the week after being tagged by another fitness/health
  creator get about 10% more engagement than their own usual, and random times show nothing. This is the first
  between-creator test to pass its pre-registered mark. Stated with it: it is the plan's SECONDARY test (the plan says
  Test 2 is not to be reported as the main finding); the first run on 365 days (116 events) pointed the same way
  (+4%) but was not significant; the lower end of the interval is close to 0 (+0.5%). Commenters themselves did not
  move from A to B (Test 1), so the lift is in views and likes, not in the same people commenting. Not re-run.

# Between-creator spillover with the method that detected within-creator spillover: plan fixed before any number (10 Nov 2026, ~21:30 IST)

Agreed with Shimona on 10 Nov 2026 ("find more events ... accordingly to the requirements of spillover"). Written before
any F, p or per-pair number of this test was computed. Known when writing: 257 tag pairs (models/audience_flow_events_rep_9nov.json)
and 240 joint-video events (models/joint_video_events_9nov.json), counted only. Every earlier result stays reported as it is;
this is a NEW question, not a re-run of a null test.

## Why
The event tests (tags, joint videos, brands) looked only 7-30 days around a few hundred events and could see only large
effects. The one detected result (scripts/run_platform_pairs.py) uses every day of a year per creator. This test applies
that same method BETWEEN creators: does creator A's posting predict comments on linked creator B's older videos?

## Pairs (identity only)
- PRIMARY: directed pairs (A, B) where A @tagged B at least once in the 730 days to 9 Nov 2026 (the replication tag list,
  models/audience_flow_events_rep_9nov.json, unchanged).
- SECONDARY: directed pairs (A = host, B = named creator) from the joint-video events (models/joint_video_events_9nov.json).
- A pair is used if A has >= 5 posts in the window and B's series is not constant.

## Series (last 365 days, UTC days, same as the detected test)
- X_A = A's posts per day: YouTube uploads + Instagram posts.
- Y_B = log1p(comments arriving that day on B's YouTube videos older than 72 h) (removes B's own upload effect).
- Pooled Granger F, lags 1-3, each pair's own mean removed: run_platform_pairs.granger_f, unchanged.

## Two checks, both needed
1. TIMING placebo: X_A circularly shifted by a random 10-300 days per pair, 500 runs, seed 5 (as in the detected test).
2. UNLINKED placebo (rules out "everyone is busy in the same weeks", e.g. festivals, January): for every pair keep B and
   replace A with a random A' from the creators who are A in some primary pair, A' never linked to B in either list or
   direction; 500 draws, seed 0. p = share of draws with F >= real F.

DETECTED (between-creator) only if >= 20 pairs AND timing p < 0.05 AND unlinked p < 0.05. Otherwise NOT detected.
Secondary uses the same rule. Fewer than 20 pairs: printed, not a result.

## Not allowed
Changing the pair lists, the lags, the windows, the 72 h cut, the series or the pass rule after seeing numbers; running
again until it passes. Run once (scripts/between_creator_granger_test.py -> models/between_creator_granger_10nov.json);
the result is reported beside every other spillover result whatever it shows. Granger is prediction, not proof of cause.

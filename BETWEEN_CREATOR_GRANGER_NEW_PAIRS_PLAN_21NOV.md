# Between-creator Granger, confirmation on NEW tag pairs (plan fixed 21 Nov 2026, ~20:45 IST, before any number)

Agreed with Shimona (21 Nov: "make it detected ... do that part"). BETWEEN_CREATOR_GRANGER_PLAN_10NOV.md was run once on
10 Nov (257 tag pairs listed, 238 used): timing p 0.002, unlinked p 0.0539 -> NOT detected. That plan forbids running it
again, and it is NOT run again. This plan asks the same question on pairs it never saw, as the tag confirmation did on
12 Nov (TAG_ENGAGEMENT_CONFIRMATION_PLAN_12NOV.md). Known when writing: the 10 Nov result above and the count of new
pairs below (identity only); no F, p or series of the new pairs has been computed.

## Pairs (identity only)
- NEW pairs: directed (A, B) in models/audience_flow_events_rep_9nov_final21nov.json (the same tag builder re-run on the
  complete data of 21 Nov) whose pair, in either direction, is NOT in models/audience_flow_events_rep_9nov.json: 67 pairs.
  They exist mainly because Instagram handles of 157 creators were added on 11 Nov and 9 small creators on 17 Nov.
- No secondary list (all joint-video pairs were already tested or are linked to tested pairs).

## Test (unchanged code and rules of the 10 Nov plan; scripts/between_creator_granger_test.py with GRANGER_NEW_PAIRS=1)
- Series: last 365 days to the run day, X_A = A's posts per day (YouTube + Instagram), Y_B = log1p(comments on B's
  YouTube videos older than 72 h); pooled Granger F, lags 1-3, run_platform_pairs.granger_f unchanged; pair used if A
  has >= 5 posts and both series vary.
- Timing placebo: 500 circular shifts of 10-300 days, seed 5. Unlinked placebo: B kept, A replaced by a random A' from
  every creator who tags in either list, A' never linked to B in any tag or joint-video list (old or 21 Nov), 500 draws, seed 0.
- DETECTED only if >= 20 pairs used AND timing p < 0.05 AND unlinked p < 0.05. Fewer than 20 used: printed, not a result.

## Rules
Run once (models/between_creator_granger_newpairs_21nov.json). Reported next to the 10 Nov result whatever it shows; a
pass is "suggestive, confirms on new pairs" (about 25 tests run in the project); the 10 Nov null is not replaced.
Granger is prediction, not proof of cause.

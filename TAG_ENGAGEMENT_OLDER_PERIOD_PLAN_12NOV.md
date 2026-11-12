# Second confirmation of tag -> 7-day engagement: an OLDER, non-overlapping period (plan fixed 12 Nov 2026, before any data)

Written on 12 Nov 2026 night, BEFORE the older YouTube history was fetched and before any event list or outcome of this
plan existed. Agreed with Shimona ("then confirm this", 12 Nov).

## Context, stated in advance
- Replication (AUDIENCE_FLOW_PLAN_8NOV.md, tags 10 Nov 2024 - 9 Nov 2026): Test 2 DETECTED, +0.095 [+0.005, +0.185],
  291 events.
- First confirmation (TAG_ENGAGEMENT_CONFIRMATION_PLAN_12NOV.md, 35 new pairs): 42 events, -0.115 [-0.339, +0.122],
  NOT detected (too small to confirm or rule out).
- This is a second, separate confirmation on a period the replication never used. All three results are reported
  together, whatever this one shows. No further confirmation attempts will be added to this question before 21 Nov.

## Data step (before any event is built)
scripts/ingestion/youtube_backfill_history.py --days 1470 for the verified creators (adds older videos only; no
deletes), within the shared daily quota (at most 3,000 units on 12 Nov, the rest after the 13 Nov reset). The test runs
once the backfill has finished.

## Events
Same identity rule as the replication (scripts/audience_flow_test.py build_events): YouTube video or Instagram post by
A with the @handle of held, in-scope B; first tag of B by A within 30 days; A and B both have YouTube videos; no
self-tags; handles as held on the day of the run. Window: **10 Nov 2022 to 9 Nov 2024** (730 to 1,460 days before
9 Nov 2026), which does not overlap the replication's window. Pairs may repeat from the replication; the period does not.

## Test (unchanged Test 2, same code: audience_flow_test.engagement_change)
B's YouTube videos at least 14 days old; engagement = log(views + likes + 1) minus B's own median for the same kind
(Short or long); effect = mean over B's videos in the 7 days after the tag minus mean in the 30 days before.
Placebo: 5 random times per event inside the same older window, no tag of B within 30 days; seed 1.
Pass mark: DETECTED only if the 95% interval of the mean effect (bootstrap over creator pairs, 2,000 draws, seed 0) is
above 0 AND the placebo interval includes 0. Fewer than 20 counted events: printed, not a result.

## Rules
Run once (scripts/tag_engagement_older_period_test.py run); no change to windows, thresholds or events after any
number is seen; reported next to the replication and the first confirmation.

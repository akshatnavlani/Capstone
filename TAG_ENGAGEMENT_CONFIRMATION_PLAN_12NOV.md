# Confirmation of the tag -> 7-day engagement result on NEW creator pairs (plan fixed 12 Nov 2026, before any number)

Written on 12 Nov 2026 evening, after the replication of AUDIENCE_FLOW_PLAN_8NOV.md found Test 2 (secondary) DETECTED
(+0.095, 95% CI [+0.005, +0.185], 291 events). Written BEFORE the new event list was built and before any outcome of
this plan was computed. Agreed with Shimona ("collect more so that more spillover can be detected", 12 Nov).

## Why
A single detected secondary result can be chance. The honest way to strengthen it is not to re-run it with more data,
but to test the same thing, unchanged, on creator pairs it never saw. New pairs exist because Instagram handles of 157
in-scope creators were added on 11 Nov (from their own YouTube descriptions and About pages), so tags of them are now
recognised in old posts.

## Events (identity rules only, same as the replication)
- Same rule and window as the replication (scripts/audience_flow_test.py build_events with --rep): a YouTube video or
  Instagram post by creator A whose title, description or caption has the @handle of a held creator B, in the 730 days
  before 9 Nov 2026; first tag of B by A within 30 days; B in scope; A and B both have YouTube videos; self-tags excluded.
- Handles as held in the database on 12 Nov 2026.
- **NEW pairs only:** every (A, B) pair that appears in models/audience_flow_events_rep_9nov.json is removed, with all
  its events. The list is written to models/tag_confirmation_events_12nov.json.

## Test (exactly Test 2 of AUDIENCE_FLOW_PLAN_8NOV.md, same code: audience_flow_test.engagement_change)
- B's YouTube videos at least 14 days old (same cutoff date as the replication); engagement = log(views + likes + 1)
  minus B's own median for videos of the same kind (Short or long). Effect per event = mean over B's videos in the 7 days
  after the tag minus mean over B's videos in the 30 days before.
- Placebo: 5 random times per event in the same 730 days, with no tag of B (from either event list) within 30 days;
  seed 1.
- Pass mark: DETECTED only if the 95% interval of the mean effect (bootstrap resampling creator pairs, 2,000 draws,
  seed 0) is above 0 AND the placebo interval includes 0. Fewer than 20 counted events: printed, not a result.

## Rules
Run once (scripts/tag_engagement_confirmation_test.py run); report the result whatever it is, next to the replication;
no change to windows, thresholds or the event list after any number is seen. B creators can overlap with the
replication (same B, different A); this is stated with the result.

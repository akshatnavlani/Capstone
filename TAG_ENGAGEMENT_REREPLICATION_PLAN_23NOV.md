# Tag -> tagged creator's 7-day engagement: re-test on never-tested events (plan fixed 23 Nov 2026, before the run)

Asked by Shimona (23 Nov: "do the test again now lets see"), after Eesha's review that the +10% tag result was
detected once and not replicated.

## Why this is a real re-test, not a re-run
Re-running the 9 Nov replication on the same events would print the same number. Since then the history backfill added
tag events dated inside the same window (9 Nov 2024 - 9 Nov 2026) that the +10% run never saw:
- `models/audience_flow_events_rep_9nov.json`: 441 events, the +10% run (291 counted; +0.095 [+0.005, +0.185], DETECTED).
- `models/audience_flow_events_rep_9nov_final21nov.json`: 662 events (same rule, data of 21 Nov): 230 not in the 9 Nov list.
- `models/tag_confirmation_events_12nov.json`: 86 of those 230 were already tested on 12 Nov (-0.115, NOT detected).
- **This test: the remaining 144 events**, never used by any simple test. (They were inside the GAIL-R final run's
  pooled lists, a different method; no simple-test number on them exists.)

## Method (identical to the 9 Nov replication, test 2)
`scripts/tag_engagement_rereplication_test.py run`, once. Outcome `audience_flow_test.engagement_change` on the tagged
creator (7 days after vs before, log scale), replication constants (730 days, NOW = 9 Nov 2026); placebo dates drawn the
same way (seed 1, at least 30 days from any known tag of that creator, using all three lists); creator-pair bootstrap
`boot_ci`. Results to `models/tag_rereplication_results_23nov.json`; the script refuses to run twice.

## Reading (fixed now)
- DETECTED only if at least 20 events are counted, the 95% interval is above 0 and the placebo interval includes 0.
- Otherwise NOT detected. Fewer than 20 counted: printed, not a result.
- Power, stated before the run: the 9 Nov run's SE was about 0.046 on 291 counted events; with about 95 counted
  (the same share of 144) SE is about 0.08, so a true +10% effect would be detected only about 20-30% of the time.
  A non-detection therefore mostly reflects the small sample; a detection would be a genuine replication.
- Whatever the result, it is reported next to the earlier four (first run +0.040, 9 Nov +0.095, older period +0.050,
  new pairs -0.115), and the app and paper wording follow the full set, not this run alone.

## Result (run once, 23 Nov 2026 ~21:00; models/tag_rereplication_results_23nov.json)
- 144 events, 98 counted (43 pairs): effect **+0.037 [-0.091, +0.160]** (about +3.7%, range -8.7% to +17.4%).
  Placebo -0.023 [-0.166, +0.107] (includes 0). **NOT detected.**
- Reading: positive, not significant, as the stated power (about 20-30%) made likely. The 9 Nov estimate (+0.095) lies
  inside this interval, so it neither confirms nor contradicts it. Tag result across five event sets: first run +0.040,
  9 Nov +0.095 (DETECTED), older period +0.050, new pairs -0.115, this re-test +0.037: detected once, not replicated.

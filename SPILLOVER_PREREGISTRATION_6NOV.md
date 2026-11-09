# Spillover test: plan fixed before the re-run (6 Nov 2026, 23:30 IST)

Written BEFORE any model is re-run on the data collected on 6-7 Nov 2026. Whatever the result, it is reported
against this plan. A change after seeing results is reported as a change, with the original result kept.

## Question
When creator A runs a fitness or health sponsorship, does the engagement of a linked fitness or health creator B
change compared with B's own trend (spillover)?

## Data added for the re-run (chosen on identity only, never on outcomes)
- Event labels: data/event_brand_labels.csv, 92 hand labels kept, 2,564 added from brand type
  (scripts/label_events_by_brand_type.py; rule: every fitness or health brand = yes; makeup, skincare, lifestyle,
  other consumer = no). Events with no brand stay unlabelled (excluded). Standing affiliate codes are not events
  (1 Nov rule; Yash Anand's 60 unbranded MuscleBlaze-code videos deliberately not branded).
- Creators: 130 Indian fitness, sport, yoga/meditation and health YouTube creators mentioned by a sponsored creator
  (models/collaborator_shortlist_6nov.json, rule inside the file), 2 years of videos each.
- Older videos for 20 in-scope channels whose stored history was under 2 years (teams, leagues, yoga, Swami Ramdev,
  Vikram Singh Fitness, Sania Mirza ...).
- Scope: data/creator_scope_overrides.csv, health and yoga/meditation creators = yes (user 2026-11-06).

## Primary test (unchanged method)
- Code: scripts/train_prod_model.py at the commit that contains this file, default settings
  (GAIL_EVENTS=fitness, GAIL_CREATORS=fitness, 30-day windows, GAIL_KEEP_SELF_SPONSORED=0).
- Links: creator_related_accounts relations as in the repo. Shared-brand links (SHARED_BRAND_TARGETS) are NOT used
  in the primary test; if run, reported separately as a different relation.
- Estimate: GAIL-R with the placebo penalty (ml/gail_r.py), bootstrap interval.

## Pass mark
- Spillover DETECTED only if the 95% interval of the GAIL-R estimate excludes 0 AND the placebo (pre-period)
  estimate's interval includes 0.
- With fewer than 8 exposed observations the estimate is printed but is not a result (MIN_EXPOSED_FOR_ESTIMATE).
- Otherwise the finding is a bounded null: report the interval and the smallest effect the data could have seen
  (power analysis, ml/ and models/power_analysis.json method).

## Added 7 Nov 2026, 15:15 IST, before any re-run (no result seen)
After the new videos were labelled (scripts/ingestion/label_new_videos.py, 286 marked) and the 1 Nov standing-code
rule applied (6 un-flagged), two creators carry most new sponsored videos: Varun dutt dubey (151 of 400 videos) and
Manish Keshwani Fitness (63 of 400). Their descriptions carry a discount code under most videos with changing
wording, which the 1 Nov rule (same brand in >= 50% of videos within +-30 days) does not catch. No post is changed
by hand. One sensitivity run is added: the primary test repeated without creators whose sponsored share of stored
videos exceeds 25% ("affiliate-heavy"). The primary result stays the primary result; both are reported.

## Secondary test (Track B, published design)
Subscriber growth of B in the 0-2 days after A's collaboration or sponsorship, from profile_snapshots (every 2 hours
since 6 Nov 2026 via GitHub Actions). Run when at least 30 events have readings on both sides; same pass-mark logic.

## Not allowed
Dropping creators, events or links after seeing results; choosing windows or settings by which gives a significant
result; reporting only the best of several runs. Every run made is listed.

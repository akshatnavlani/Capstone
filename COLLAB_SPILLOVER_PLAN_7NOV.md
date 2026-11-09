# Collaboration spillover (published design): plan fixed before any data (7 Nov 2026)

A SEPARATE question from the sponsorship-spillover test (SPILLOVER_PREREGISTRATION_6NOV.md, result: not detected,
SPILLOVER_RESULTS_7NOV.md). That result stands and is reported as it is; this study does not replace it.

## Question
When creator A tags creator B (both held, both Indian fitness/health/sport/yoga in scope), does B gain YouTube
subscribers faster in the 0-48 hours after the tag than B's own rate just before? Follows Koch et al. (2018):
collaborations brought subscriber gains within 0-2 days, mostly for channels under 100k.

## Data (collected forward from 7 Nov 2026; nothing before this date is used)
- Subscriber counts every 2 hours for all 364 held YouTube channels (scripts/ingestion/snapshot_youtube_profiles.py
  in the GitHub Actions timer; widened from 147 verified channels on 7 Nov).
- Events: a YouTube video or Instagram post by A whose title, description or caption has @handle of B (B's held
  YouTube or Instagram handle), published on or after 7 Nov 2026. Only the first tag of B by A within 30 days counts.
  Self-tags and brand accounts excluded. B must be in scope (creator rule of train_prod_model.py with
  data/creator_scope_overrides.csv).

## Measure
growth_after = log(subs at t+48h / subs at t), growth_before = log(subs at t / subs at t-48h), from the nearest
readings (within 3 h). Effect per event = growth_after - growth_before.
Placebo: the same difference at 200 random times per B with no tag of B within 7 days.

## Test and pass mark
- Primary: mean effect over events, 95% interval from a bootstrap that resamples B creators.
- DETECTED only if the interval is above 0 AND the placebo interval includes 0.
- Subgroup (reported, not the pass mark): B under 100k subscribers.
- Run once when at least 30 events have readings on both sides (expected around 21 Nov 2026 at about 21 tags a
  week), then report whatever it shows, with every run listed.

## Not allowed
Changing the window, the event rule or the creators after seeing data; running repeatedly until a significant
result appears; reporting the subgroup as the main result.

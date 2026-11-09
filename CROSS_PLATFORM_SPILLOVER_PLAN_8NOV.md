# Cross-platform sponsorship spillover (same creator): plan fixed before any number (8 Nov 2026)

Agreed with Shimona on 8 Nov 2026 ("Idea A"), written before any count. Builds on her cross-platform lag finding
(models/platform_pairs.json: the two platforms move together within 1-3 days, Granger p 0.002-0.008).
Reported beside the other spillover results whatever it shows.

## Question
When a creator publishes a sponsored post on one platform, does the same creator's engagement on the OTHER platform
change in the following 7 days, compared with that creator's own usual?

## Events
- A dated sponsored post (Instagram: is_sponsored or paid-partnership label; YouTube: is_sponsored) whose id has
  fitness = yes in data/event_brand_labels.csv, by an in-scope creator (creator rule with
  data/creator_scope_overrides.csv) who also has posts on the other platform.
- Only the first such event per creator and platform within 14 days (later ones in a burst are not separate events).

## Measure
- Other-platform posts: the creator's posts on the other platform that are NOT sponsored, at least 14 days old (counts
  settled). Engagement = log(likes + comments + 1) (YouTube: log(views + likes + 1)) minus the creator's median on
  that platform (YouTube: same kind, Short or long).
- Effect per event = mean over other-platform posts in the 7 days after the event minus mean over those in the 30 days
  before. An event counts only with at least 1 post on each side.
- Placebo: 5 random times per event for the same creator and direction, with no sponsored post by that creator on
  either platform within 14 days. Seed 0.

## Test and pass mark
- Primary: both directions pooled. 95% interval of the mean from a bootstrap over creators.
- DETECTED (positive or negative) only if the interval excludes 0 AND the placebo interval includes 0.
- Each direction (YouTube -> Instagram, Instagram -> YouTube) reported, not the pass mark.
- Fewer than 20 counted events: printed, not a result.

## Not allowed
Changing windows, the event rule or thresholds after seeing numbers; re-running until something passes.

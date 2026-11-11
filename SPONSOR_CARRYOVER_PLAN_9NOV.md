# Sponsorship spillover onto the creator's own other videos: plan fixed before any count (9 Nov 2026)

Agreed with Shimona on 9 Nov 2026. A DIFFERENT kind of spillover from the creator-to-creator tests (all not detected,
AUDIENCE_FLOW_RESULTS_8NOV.md): does a sponsorship spill over from the sponsored video into the conversation on the
same creator's OTHER, non-sponsored videos? (advertising spillover / carry-over in the marketing literature).
Written before any comment was searched for this question. Every result is reported.

## Events
- Creator A's dated sponsored YouTube video with a brand (brands table) whose id has fitness = yes in
  data/event_brand_labels.csv; A in scope (creator rule with data/creator_scope_overrides.csv).
- Only the first event per (A, brand) within 60 days.

## Measure
- Brand mention = a comment containing the brand's name or one of its aliases (scripts/ingestion/known_brands.py,
  same pattern as scripts/brand_spillover_test.py), whole words, case-insensitive.
- Videos counted: A's own YouTube videos that are NOT sponsored by that brand, and not the event video, in the 30 days
  before and the 30 days after the event (up to 5 per side, the most-commented, as in the other tests).
  A's videos sponsored by the same brand anywhere in either window are left out.
- Comments: those already held in youtube_comments (no new fetch for this run).
- Effect per event = brand mentions per 1,000 comments after minus before; an event counts with at least 50 comments
  on each side.
- Placebo: the same (A, brand) at 5 random times in the 730 days before 9 Nov 2026 with no sponsorship of that brand
  by A within 60 days (seed 0).

## Test and pass mark
DETECTED only if the 95% interval of the mean effect (bootstrap over creators, 2,000 draws, seed 0) is above 0 AND
the placebo interval includes 0. Fewer than 20 counted events: printed, not a result.

## Not allowed
Adding brands or aliases, or changing windows or thresholds, after seeing counts. Calling this creator-to-creator
spillover: it is spillover within a creator's channel, from sponsored to non-sponsored content.

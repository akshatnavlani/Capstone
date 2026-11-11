# Brand-awareness spillover through the creator network: plan fixed before any count (8 Nov 2026)

Agreed with Shimona on 8 Nov 2026 ("Idea B"), written before any comment was searched for brands.

## Question
After creator A publishes a sponsored post for fitness brand X, do comments on a LINKED creator B's videos mention
brand X more than before?

## Events
- A's dated sponsored post with a brand (brands table) whose id has fitness = yes in data/event_brand_labels.csv.
- B linked to A: a creator_related_accounts row of A pointing to B's handle, or A @mentioning B's handle in any
  post (the tag rule of AUDIENCE_FLOW_PLAN_8NOV.md). B in scope, B on YouTube, B != A.
- B must NOT have a sponsored post for brand X within 60 days of the event (otherwise B's own ad explains mentions).
- Only the first event per (A, B, brand) within 30 days.

## Measure
Brand mention = a comment containing the brand's name or one of its aliases from scripts/ingestion/known_brands.py
(whole words, case-insensitive). Comments: on B's top 5 videos (by comment count) in the 30 days before and the 30 days
after the event, fetched with scripts/ingestion/youtube_comments_backfill.py --video-ids-file.
Effect per event = brand mentions per 1,000 of B's comments after minus before; an event counts with at least 50
comments on each side.
Placebo: the same (B, brand) at 5 random times (seed 0) with no sponsored post for that brand by A or B within 60 days.

## Test and pass mark
DETECTED only if the 95% interval of the mean effect (bootstrap over creator pairs) is above 0 AND the placebo
interval includes 0. Fewer than 20 counted events: printed, not a result.

## Not allowed
Adding brands, aliases or phrases after seeing counts; changing windows or thresholds after seeing numbers.

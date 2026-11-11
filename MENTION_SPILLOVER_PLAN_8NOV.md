# "Came from A" comments: direct evidence of spillover. Plan fixed before any count (8 Nov 2026)

Agreed with Shimona on 8 Nov 2026, written before any comment was searched. Reported beside SPILLOVER_RESULTS_7NOV.md
and AUDIENCE_FLOW_RESULTS_8NOV.md, whatever it shows.

## Question
After creator A tags creator B, do comments on B's videos start naming A (viewers saying, in effect, "I came from A")?

## Data (already collected; nothing new chosen)
The 159 tag events of models/audience_flow_events_7nov.json and the comments fetched for AUDIENCE_FLOW_PLAN_8NOV.md
(B's top 5 videos in the 30 days before and in the 30 days after each tag; placebo times as in that plan).

## Measure
A comment on B's video "names A" when it contains A's YouTube or Instagram handle (with or without @), or A's full
display name (the part before any bracket), matched as whole words, case-insensitive; A's name only if it has at least
6 letters (so short common words do not count). Rate = comments naming A per 1,000 of B's comments.
Effect per event = rate after - rate before.

## Test and pass mark
- Primary: mean effect over events with at least 50 of B's comments on each side; 95% interval from a bootstrap over
  creator pairs. DETECTED only if the interval is above 0 AND the same measure at the placebo times has an interval
  that includes 0.
- Also reported (not the pass mark): how many events have at least one comment naming A after the tag but none before,
  with up to 10 example comments (as written, names of commenters removed).

## Not allowed
Changing the name rule, windows or thresholds after seeing counts; adding phrases after looking at comments.

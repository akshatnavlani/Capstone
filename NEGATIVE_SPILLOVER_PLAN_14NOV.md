# Negative spillover: does a creator's bad audience moment hurt linked creators? (plan fixed 14 Nov 2026, 22:50, before any data)

Agreed with Shimona (14 Nov: "negative spillover, actually try to measure how much"). The app's risk alerts assume that a
creator's negative audience mood spreads to linked creators; this tests it. Written before any comment was scored for
this purpose and before any event or outcome existed.

## Links (identity rules only, built before any mood score)
Undirected creator pairs (A, B) that are linked by any of: a tag event (models/audience_flow_events_rep_9nov.json,
models/tag_older_period_events.json), a joint video (models/joint_video_events_9nov.json, joint_video_events_9nov_older.json),
or a listed related account that is a held creator (creator_related_accounts). B must be in scope.

## Mood per video (scoring step)
For every YouTube video of a linked creator published 10 Nov 2024 - 9 Nov 2026 with at least 30 stored comments: score up
to 50 of its stored comments (most-liked first) with the project's mood models (twitter-roberta-base-sentiment-latest for
Latin script, twitter-xlm-roberta-base-sentiment for Devanagari script), mood = P(positive) + 0.5 P(neutral) (the app's
formula); video mood = mean over its scored comments. Saved to models/video_mood_14nov.json.

## Events ("bad moments")
A video of creator A whose mood is below A's own 10th percentile AND below 0.5, for creators A with at least 10 scored
videos; only the first such video per A within 30 days. Event time = the video's publish time.

## Outcome and test (same outcome code as the tag test: audience_flow_test.engagement_change)
For each linked B of A: B's engagement (log(views + likes + 1) minus B's own median for the same kind) in the 7 days after
the event minus the 30 days before; videos at least 14 days old.
Placebo: 5 random times per (event, B) in the same window, with no bad moment of A within 30 days; seed 1.
- NEGATIVE spillover DETECTED only if the 95% interval of the mean effect (bootstrap over (A, B) pairs, 2,000 draws,
  seed 0) is entirely BELOW 0 and the placebo interval includes 0. A positive interval is reported as such.
- Secondary (reported separately, same mark): B under 100,000 subscribers.
- Fewer than 20 counted events: printed, not a result.

## Rules
Run once; reported whatever it shows. Multiple testing: one more test on top of about nineteen; a single pass is
"suggestive, needs confirmation". scripts/negative_spillover_test.py; results models/negative_spillover_results_14nov.json.

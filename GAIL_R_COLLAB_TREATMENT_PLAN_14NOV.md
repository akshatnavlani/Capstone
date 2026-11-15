# GAIL-R with collaboration treatments: joint videos and tags (plan fixed 14 Nov 2026, 23:00, before any code or run)

Agreed with Shimona (14 Nov: "other spillover should also be connected to GAIL-R ... do it"). So far GAIL-R has measured
one treatment, a paid sponsorship. The simple tests found spillover through collaborations instead (joint video, small
creators +0.277 in the older period; tags +0.095 in the replication, +0.050 in the older period). This plan points the
same validated estimator at those treatments. Written before any code change or result for this question.

## What changes (one switch, GAIL_TREATMENT; default "sponsorship" = today's behaviour)
- GAIL_TREATMENT=joint_video: an EVENT is a joint video by creator A (models/joint_video_events_9nov.json and
  joint_video_events_9nov_older.json: A's video naming / tagging B), dated by the video's publish time.
- GAIL_TREATMENT=tag: an EVENT is a tag of another held creator by A (models/audience_flow_events_rep_9nov.json and
  tag_older_period_events.json).
- For both, the event's pair (A, B) is added as a `collaborates_with` edge, so that the creator who was featured or
  tagged is a neighbour of A (otherwise the person most likely to gain could not be measured).
- Everything else is unchanged: observations, 30-day windows, format split, settled posts, self-event rows dropped,
  window effects, attention shrinkage, placebo penalty 30, creator-level bootstrap B = 200, seed 0.

## Reading (fixed now)
- Detected only if the 95% interval of the effect on exposed observations (placebo penalty 30) is above 0.
- Secondary, reported separately: exposed observations whose neighbour has under 100,000 subscribers (the subgroup in
  which the simple joint-video test found the effect), if at least 20 such observations exist.
- Each variant runs once; both are reported whatever they show, next to the sponsorship result. Multiple testing as in
  OLDER_PERIOD_REPLICATIONS_PLAN_14NOV.md: a single pass is "suggestive".
- The app's model files are backed up and restored around each run, as in GAIL_R_UPDATE_PLAN_14NOV.md.

Note added 15 Nov 2026, 00:05 (16 Nov), before any corrected result: an implementation error was found. The first
joint-video run (finished 23:38, GAIL_R_RESULTS_15NOV.md section 2) added each event pair only to pair_count's pairs,
not to the model's collaborates_with graph, contrary to this plan (its log shows the same 924 graph edges as the
sponsorship run). The tag run started 23:38 had the same error and was stopped before printing any estimate. The code
is fixed (scripts/train_prod_model.py adds the event pairs to the model graph) and both variants are re-run once as the
plan intended; the first joint-video result is kept and reported as "run with the graph error".

# GAIL-R on the featured/tagged creator of ANY collaboration (tags + joint videos pooled), 7 days
(plan fixed 16 Nov 2026, 15:20, before any code change or number of this variant, and before the tagged-creator run
of GAIL_R_FEATURED_TAG_PLAN_16NOV.md has started)

Agreed with Shimona (16 Nov: "make it detected ... do something"). GAIL-R's collaboration results so far are all
positive and none detected: featured joint-video creator +0.0086 (small +0.0674, 72 exposed), all joint-video
neighbours +0.0305 [-0.0529, +0.1006] (GAIL_R_RESULTS_15NOV.md sections 2-3). The limit is the number of exposed
creators, not the direction. The study's question is whether COLLABORATING spills over to the partner; tags and joint
videos are both collaborations. Pooling them is the largest honest sample available this week. Results known when
writing: the joint-video runs above; no tag GAIL-R number (the tag runs have not started).

## Run (one, after the tagged-creator run)
GAIL_TREATMENT=collab GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 GAIL_R_SMALL_B=1
- Events (no list rebuilt or edited): joint videos (joint_video_events_9nov.json, _older.json: 776) + tags
  (audience_flow_events_rep_9nov.json, tag_older_period_events.json, tag_confirmation_events_12nov.json: 1,391).
  A collaboration found in both lists (same creator A, same creator B, same day) is counted once.
- Observation: the (collaboration, featured/tagged creator B) pair only; the pair is added to the model graph.
- Outcome: B's engagement in the 7 days after, baseline 30 days before. 7 days because most events are tags and the
  detected simple tag result used 7 days (fixed now, not chosen from any GAIL-R number).
- Unchanged: window effects, format split, settled posts, attention shrinkage, placebo penalty 30, creator bootstrap
  B = 200, seed 0; app model backed up and restored.

## Reading (fixed now)
- Primary: all featured/tagged creators. DETECTED only if the 95% interval of the effect on exposed observations
  (placebo penalty 30) is above 0 with at least 20 exposed observations. Secondary: under 100,000 subscribers.
- Run once; reported whatever it shows, with every other GAIL-R run (7th spillover variant). Overlap: it contains the
  events of the tagged-creator run and of the featured joint-video run, so it is not independent of them; a pass is
  reported as "suggestive" and as pooled evidence, never as a separate confirmation.

Count after the code change (events only, no outcome computed): 1,573 pooled events (594 found in both lists counted
once), 703 creator pairs. joint_video (776) and tag (1,305 default; 1,391 with the switch) unchanged.

Note added 16 Nov 2026, 21:05, before this run has started and before any pooled number (the tagged-creator run is
running; no tag-featured number yet). The same event builders were re-run on 16 Nov data into new files (originals
untouched, checked by md5): joint videos 294 recent + 536 older (joint_video_events_9nov[_older]_count16nov.json), tags
653 recent + 864 older (audience_flow_events_rep_9nov_count16nov.json, tag_older_period_events_count16nov.json). The
pooled run uses the earlier lists AND these, each (A, B, day) once: 1,727 events, 732 pairs (was 1,573 / 703). Reason:
116,082 YouTube videos arrived after 9 Nov (history backfill), so the earlier lists missed tags in them. Nothing else
changes; joint_video and tag modes are unchanged (776 / 1,391 events).

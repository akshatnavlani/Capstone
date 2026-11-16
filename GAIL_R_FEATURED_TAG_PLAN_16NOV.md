# GAIL-R on the TAGGED creator, 7 days (plan fixed 16 Nov 2026, 13:55, before any code change or number of this variant)

Agreed with Shimona (16 Nov: "do something try and detect it please ... for gail"). The simple tag test (Test 2 of
AUDIENCE_FLOW_PLAN_8NOV.md, replication) DETECTED +0.095 [+0.005, +0.185] on the TAGGED creator B, 7 days after vs 30
days before. GAIL-R has not yet been asked that question: the queued tag run (GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md)
measures every neighbour of the tagging creator A over 30 days. The featured joint-video run (16 Nov, GAIL_R_RESULTS_15NOV.md
section 3) showed that GAIL-R's limit there was the number of featured creators (72 small); tags give about twice as
many events. Results known when writing: the joint-video runs only (sections 2 and 3); no tag GAIL-R number yet.

## Run (one, after the 16 Nov queue finishes)
GAIL_TREATMENT=tag GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_TAG_CONFIRMATION=1 GAIL_R_SMALL_B=1
- Events: every tag event already built: models/audience_flow_events_rep_9nov.json (441), tag_older_period_events.json
  (864), plus (new switch GAIL_TAG_CONFIRMATION=1) tag_confirmation_events_12nov.json (86): 1,391 events. No event list
  is rebuilt or edited. The default (switch off) is unchanged, so the queued tag run is not affected.
- Observation: the (tag, tagged creator B) pair only (featured-only mode, as in section 3); the event pair is added to
  the model's collaborates_with graph (16 Nov fix).
- Outcome: B's engagement in the 7 days after the tag, baseline 30 days before (the simple test's windows).
- Unchanged: window effects, format split, settled posts (as the code sets them), attention shrinkage, placebo penalty
  30, creator-level bootstrap B = 200, seed 0; app model backed up and restored.

## Reading (fixed now)
- **Primary: all tagged creators** (the simple test's +0.095 was for all B). DETECTED only if the 95% interval of the
  effect on exposed observations (placebo penalty 30) is above 0, with at least 20 exposed observations.
- Secondary: tagged creators under 100,000 subscribers (printed by GAIL_R_SMALL_B=1), reported, not a pass mark.
- Run once; reported whatever it shows, next to every other GAIL-R run. Multiple testing: this is the 6th GAIL-R
  spillover variant, so a single pass is reported as "suggestive" and as "GAIL-R agrees with the simple tag test"; a
  null as "GAIL-R cannot confirm it". No re-run, no change of window or events after any number is seen.

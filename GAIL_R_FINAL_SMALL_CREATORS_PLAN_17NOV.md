# Final GAIL-R run on the complete dataset: small creators, pooled collaborations (plan fixed 17 Nov 2026, 01:30,
before the data it will use exists)

Agreed with Shimona (17 Nov: "we want to do it through gail r as well ... do something"). After the 16 Nov runs
(GAIL_R_RESULTS_15NOV.md sections 3-8), every GAIL-R collaboration estimate is positive and none is detected. The
all-creator estimates are about +1% to +3%; the small-creator (<100k) estimates are the largest: tagged creator +0.161
[-0.231, +0.373], pooled +0.175 [-0.100, +0.355], focused sponsorship +0.148. The simple tests found their effects in
the same place (small creators in joint videos +0.277). Data collection continues until 20 Nov (YouTube history
backfill, daily Instagram refresh of collaborating creators).

**Disclosed choice:** small creators are made the primary reading AFTER seeing the 16 Nov results. This run is therefore
a pre-specified FOLLOW-UP on the complete dataset, not an independent confirmation, and is reported that way.

## Run (once, on 21 Nov 2026, after the history backfill stops on 20 Nov)
1. Rebuild the event lists with the same builders and rules into new files (*_final21nov.json; earlier files untouched):
   joint_video_spillover_test.py events (recent and SPILL_NOW=2024-11-09), audience_flow_test.py build-events --rep,
   tag_engagement_older_period_test.py build (pointed at a new file).
2. GAIL_TREATMENT=collab GAIL_FEATURED_ONLY=1 GAIL_OUTCOME_DAYS=7 GAIL_BASELINE_DAYS=30 GAIL_R_SMALL_B=1, using every
   earlier and rebuilt list, each (creator A, creator B, day) once (the code path of GAIL_R_POOLED_COLLAB_PLAN_16NOV.md,
   pointed at the *_final21nov.json lists). Everything else unchanged (window effects, attention shrinkage, placebo
   penalty 30, creator bootstrap B = 200, seed 0; app model backed up and restored).

## Reading (fixed now)
- Primary: featured/tagged creators under 100,000 subscribers. DETECTED only if the 95% interval (placebo penalty 30)
  is above 0 with at least 20 exposed observations. Reported as "GAIL-R follow-up on small creators", with the
  disclosed choice above and next to all 8 earlier GAIL-R runs.
- Secondary: all featured/tagged creators.
- If the rebuilt lists add fewer than 100 small-creator events over the 16 Nov pooled run, the run still happens once
  and the result is reported as "little new data".
- Run once. No further GAIL-R spillover variants after this one: whatever it shows is the final GAIL-R result for the paper.

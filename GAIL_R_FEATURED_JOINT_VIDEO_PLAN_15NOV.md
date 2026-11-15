# GAIL-R on the FEATURED creator of a joint video, 14 days (plan fixed 15 Nov 2026, 23:55, before any code or run)

Agreed with Shimona (15 Nov: "do it"). The simple older-period joint-video test (joint_video_results_9nov_older.json)
measured the creator who APPEARS in a joint video, 14 days after it, and found small creators (<100k) +0.277 [+0.113,
+0.529]. GAIL-R's joint-video run (GAIL_R_RESULTS_15NOV.md, section 2) measured every creator LINKED to a joint-video
maker over 30 days and could not tell (small creators -0.029 [-0.375, +0.395]). Both results are already known; this
plan asks GAIL-R the simple test's own question, so the two can be compared. Written before any number of this variant.

## Changes from the GAIL-R joint-video run (everything else identical)
1. Featured creator only (new switch GAIL_FEATURED_ONLY=1): an observation is the (joint video, creator B who appears
   in it) pair from the event lists; no other neighbours of A are measured.
2. Outcome window 14 days after the joint video (GAIL_OUTCOME_DAYS=14), baseline 30 days before (GAIL_BASELINE_DAYS=30).
3. Primary reading: featured creators under 100,000 subscribers (GAIL_R_SMALL_B=1); all featured creators secondary.
Unchanged: GAIL_TREATMENT=joint_video events (776), window effects, attention shrinkage, placebo penalty 30, creator
bootstrap B = 200, seed 0, the speed fix (same rows).

## Reading (fixed now)
Detected only if the 95% interval of the effect on exposed small featured creators (placebo penalty 30) is above 0 with
at least 20 exposed observations. Run once, after the overnight queue. Multiple testing: it repeats a question already
answered by the simple test, so a pass is reported as "GAIL-R agrees with the simple test", a null as "GAIL-R cannot
confirm it"; neither replaces the simple test's result.

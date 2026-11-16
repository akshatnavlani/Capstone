# GAIL-R results, 15 Nov 2026 (plans: GAIL_R_UPDATE_PLAN_14NOV.md, GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md)

Each run once; logs in models/gail_r_<name>_14nov.log, checkpoints models/gail_checkpoint_<name>_14nov.pt.
Run history (no estimate was printed by any stopped attempt): 14 Nov 21:45 start stopped before any estimate to label
1,365 new events (plan note); 14 Nov 23:00 internet drop; 15 Nov 11:09 try hung on a dropped connection (stopped 13:33);
13:35 try 1 failed on a DNS outage at 15:35 with no estimate; 15:36 try 2 completed (fast index query, same rows).

## 1. Update: paid sponsorship -> collaborators (finished 15 Nov 18:19)
4,305 dated sponsorship events (231 creators); 10,949 computable pairs; 555 exposed + 3,010 comparison observations from
387 creators (11 Nov run: 305 exposed).
- **With placebo penalty (the plan's reading): effect on exposed -0.0903, 95% CI [-0.2032, +0.0739]. NOT detected.**
  In percent: about -9% (range -18% to +8%).
- collaborates_with slope -0.117 [-0.260, +0.097]; co_occurs_with slope +1.462 [-1.985, +1.962] (wide, few links).
- Without placebo penalty: -0.0904 [-0.2036, +0.0747] (penalty ~0: no pre-trend to remove).
- Placebo (pre-trend) DiD -0.0152 (SE 0.0517): exposed and comparison creators move together before the sponsorship.
- Matched DiD (no model, observations treated as independent, interval too narrow): -0.1428 (SE 0.0676).
- Reading: with almost twice the exposed observations, still no detectable sponsorship spillover. The upper end of the
  interval is now +0.074 on the log scale, so positive spillover above about **8%** is ruled out (the 11 Nov run's bound
  was about 3%; the estimate moved toward zero and the interval narrowed from 0.33 to 0.28). Both runs are reported.

## 2. Joint video as the treatment (GAIL_TREATMENT=joint_video; finished 15 Nov 23:38)
776 dated joint-video events; 5,009 computable pairs; 1,348 observations with a joint-video collaborator in the window
(815 exposed in the GAIL-R fit) + 4,046 comparison, 396 creators.
- **With placebo penalty: effect on exposed +0.0575, 95% CI [-0.0646, +0.1374]. NOT detected** (about +6%, range -6% to +15%).
- Without placebo penalty: +0.0576 [-0.0651, +0.1381].
- collaborates_with slope +0.088 [-0.097, +0.215]; co_occurs_with -0.052 [-1.683, +1.493].
- Secondary, collaborators under 100k subscribers (pre-specified): 241 exposed, -0.0291, 95% CI [-0.3753, +0.3950].
  NOT detected; the interval is very wide (few small exposed creators per window after window effects).
- Placebo (pre-trend) DiD -0.0525 (SE 0.0498); matched DiD +0.0191 (SE 0.0449, too narrow).
- Reading: GAIL-R points the same way as the simple joint-video test for all creators (small positive, not detected) and
  cannot confirm the small-creator effect: with 241 exposed observations its interval spans -31% to +48%. Note the two
  tests define exposure differently: the simple test measures the creator who APPEARS in the joint video; GAIL-R measures
  every creator whose linked neighbour made a joint video in the window (a wider, weaker exposure).
- **Caveat found after this run:** the joint-video pairs were not added to the model graph (plan said they should be);
  this run is reported as "with the graph error" and re-run correctly (see the plan note of 16 Nov, 00:05).

## 3. Featured creator of a joint video, 14 days (GAIL_R_FEATURED_JOINT_VIDEO_PLAN_15NOV.md; 16 Nov 10:30-13:19, try 1)
Graph fix active: 448 directed event edges added to the model graph; 760 computable pairs; 10,292 observations from
395 creators; log models/gail_r_featured_jv_16nov.log, checkpoint models/gail_checkpoint_featured_jv_16nov.pt.
- **Primary (plan): featured creators under 100k, placebo penalty 30: 72 exposed of 3,320; effect +0.0674, 95% CI
  [-0.4368, +0.3980]. NOT detected -> "GAIL-R cannot confirm" the simple test's +0.277** (which lies inside this interval).
- Secondary, all featured creators: 459 exposed; +0.0086 [-0.0526, +0.1455] (without penalty +0.0086 [-0.0526, +0.1473];
  penalty chosen 0). collaborates_with slope +0.027 [-0.131, +0.375]; co_occurs_with -0.418 [-1.760, +1.639].
- Placebo (pre-trend) DiD -0.0256 (SE 0.0551): no pre-trend.
- Model-free checks (observations treated as independent, so intervals are too narrow; NOT the plan's reading):
  matched DiD +0.0898 (SE 0.0490, [-0.0063, +0.1859]); overlap-trimmed DiD +0.1167 (SE 0.0491); category-matched +0.0878
  (SE 0.0581). All point positive, in the same direction as the simple test.
- Reading: every estimate is positive (GAIL-R +1% all, +7% small; model-free +9% to +12%), none detected under the plan's
  creator-level interval. The limit is 72 small featured creators.

## 4. Joint video, corrected graph (GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md + note; 16 Nov 13:19-15:21, try 1)
448 event edges added to the model graph; 5,023 computable pairs; 5,364 observations; log
models/gail_r_joint_video_fixed_16nov.log, checkpoint models/gail_checkpoint_joint_video_fixed_16nov.pt.
- **With placebo penalty: effect on the 1,348 exposed observations +0.0305, 95% CI [-0.0529, +0.1006]. NOT detected**
  (about +3%, range -5% to +11%). Without penalty +0.0305 [-0.0533, +0.1015] (penalty chosen 0).
- collaborates_with slope +0.068 [-0.116, +0.233]; co_occurs_with -0.203 [-1.714, +1.468].
- Secondary, neighbours under 100k: 336 exposed of 1,787; -0.0565 [-0.2514, +0.1895]. NOT detected.
- Placebo (pre-trend) DiD -0.0483 (SE 0.0500); matched DiD -0.0019 (SE 0.0452, too narrow).
- Reading: with the graph error fixed, 1,348 exposed (815 before); same answer as section 2: small positive, not
  detected; positive joint-video spillover above about 11% on linked creators is ruled out.

## 5. Tag, corrected graph (GAIL_R_COLLAB_TREATMENT_PLAN_14NOV.md + note; 16 Nov 15:21-17:04, try 1)
530 event edges added to the model graph (1,305 tag events); 11,403 computable pairs; log models/gail_r_tag_fixed_16nov.log.
- **With placebo penalty: effect on the 1,856 exposed observations +0.0342, 95% CI [-0.0284, +0.1222]. NOT detected**
  (about +3%, range -3% to +13%). Without penalty +0.0342 [-0.0284, +0.1223].
- Secondary, neighbours under 100k: 538 exposed of 1,656; +0.0001 [-0.1780, +0.1627]. NOT detected.
- Placebo (pre-trend) DiD -0.0247 (SE 0.0463); matched DiD +0.0818 (SE 0.0481, [-0.0125, +0.1761], too narrow).
- Reading: small positive, not detected, on every neighbour of the tagger over 30 days (the tagged creator alone, 7 days,
  is GAIL_R_FEATURED_TAG_PLAN_16NOV.md).
Note: at 17:25 the laptop ran out of process resources (bash "fork: Resource temporarily unavailable"); the queue
stopped during mood scoring (200 of 12,592 videos, ~16 h at that pace). Remaining jobs resumed with the GAIL-R runs first
and mood scoring last (order only; scripts/run_resume_16nov.sh).

## 6. Focused paid sponsorship (GAIL_R_FOCUSED_SPONSORSHIP_PLAN_15NOV.md; 16 Nov 20:09-20:43, try 1)
Strong-evidence sponsorships only, 7-day outcome, 30-day baseline; 2,045 computable pairs; log
models/gail_r_focused_sponsorship_16nov.log.
- **Primary (plan): collaborators under 100k, placebo penalty 30: 50 exposed of 2,623; effect +0.1479, 95% CI
  [-0.3733, +0.5398]. NOT detected** (too few small exposed collaborators for a narrow interval).
- All collaborators: 247 exposed; +0.0372 [-0.1198, +0.1713] (without penalty +0.0373 [-0.1198, +0.1720]).
- collaborates_with slope +0.072 [-0.241, +0.344]; co_occurs_with 0 (no strong-sponsorship co-occurrence links).
- Placebo (pre-trend) DiD +0.0384 (SE 0.0851); matched DiD -0.0246 (SE 0.0695, too narrow).
- Reading: positive point estimates (unlike the broad update run, -0.090), not detected.

## 7. Tagged creator, 7 days (GAIL_R_FEATURED_TAG_PLAN_16NOV.md; 16 Nov 20:43-22:55, try 1)
1,391 tag events (switch GAIL_TAG_CONFIRMATION=1), featured-only; 1,331 computable pairs; log models/gail_r_featured_tag_16nov.log.
- **Primary (plan): all tagged creators, placebo penalty 30: 755 exposed; effect +0.0105, 95% CI [-0.0623, +0.1014].
  NOT detected -> "GAIL-R cannot confirm" the simple tag test's +0.095** (which lies inside this interval).
  Without penalty identical (+0.0105 [-0.0623, +0.1014]).
- Secondary, tagged creators under 100k: 157 exposed of 5,502; +0.1614 [-0.2308, +0.3731]. NOT detected.

## 8. Pooled collaborations (tags + joint videos), featured creator, 7 days (GAIL_R_POOLED_COLLAB_PLAN_16NOV.md + note 21:05; 16 Nov 22:55 - 17 Nov ~01:10, try 1)
1,727 events (earlier + 16 Nov rebuilt lists, each (A, B, day) once); 1,662 computable pairs; log
models/gail_r_pooled_collab_16nov.log.
- **Primary (plan): all featured/tagged creators, placebo penalty 30: 906 exposed; effect +0.0116, 95% CI
  [-0.0657, +0.0898]. NOT detected.** Without penalty +0.0117 [-0.0657, +0.0900].
- Secondary, under 100k: 178 exposed of 5,537; +0.1748 [-0.1001, +0.3547]. NOT detected (largest point estimate of
  any GAIL-R run; same direction as the simple small-creator joint-video result +0.277).

## Summary of the 16 Nov GAIL-R runs (each run once, plans fixed before data)
All collaboration variants positive, none detected: featured JV +0.009 (small +0.067); JV +0.031 (small -0.057); tag
+0.034 (small +0.000); tagged creator +0.011 (small +0.161); pooled +0.012 (small +0.175). Focused sponsorship +0.037
(small +0.148). Upper bounds: collaboration spillover on the partner about +9-10%; on linked creators about +10-13%.
The simple tests' detected effects (+0.095 tags, +0.277 small JV) lie inside GAIL-R's intervals: GAIL-R cannot confirm
them, and does not contradict them.

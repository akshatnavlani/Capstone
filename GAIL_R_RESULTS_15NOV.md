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

## 9. FINAL run on the complete dataset (GAIL_R_FINAL_SMALL_CREATORS_PLAN_17NOV.md; 21 Nov 19:46 - 22 Nov 00:44, try 1)
Event lists rebuilt on 21 Nov data (*_final21nov.json) and pooled with the earlier lists: 1,768 events, 754 pairs;
728 directed event edges in the model graph; 1,701 computable pairs; log models/gail_r_final_small_21nov.log.
Mood scoring ran on the same laptop at the same time (it does not touch GAIL-R's inputs).
- **Primary (plan): featured/tagged creators under 100k, placebo penalty 30: 187 exposed of 5,744; effect +0.1288,
  95% CI [-0.1000, +0.3781]. NOT detected.**
- Secondary, all featured/tagged creators: 924 exposed; +0.0176 [-0.0623, +0.0886] (without penalty +0.0176
  [-0.0625, +0.0892]). NOT detected.
- collaborates_with slope +0.046 [-0.161, +0.224]; co_occurs_with -0.031 [-1.443, +1.892].
- Placebo (pre-trend) DiD +0.0223 (SE 0.0396); matched DiD +0.0010 (SE 0.0385, too narrow).
- Reading (as fixed in the plan): this is the final GAIL-R result. Every GAIL-R collaboration estimate across 9 runs is
  positive; none is detected. The small-creator estimate (+12.9%) points the same way as the simple joint-video result
  (+27.7%), which lies inside its interval. No further GAIL-R spillover variants.

## 10. Power of the final run (22 Nov; computed from section 9's intervals, as in models/power_analysis.json of 1 Nov)
Normal approximation, SE = (CI width)/3.92; detection = 95% interval above 0. NOT a new GAIL-R run; not a result about
whether spillover exists.
- All creators (924 exposed): SE 0.0385; planted +10% detected 70% of the time, +20% 100%; 80% power from about +11%.
- Small creators (187 exposed): SE 0.1220; planted +10% 12%, +20% 32%, +30% 58%, +40% 79%, +50% 91%; 80% power from
  about +41%.
- Reading: the small-creator estimate (+12.9%) and the simple joint-video result (+27.7%) are both below GAIL-R's
  small-creator detection threshold at this sample size; its non-significance reflects sample size.

## 11. Hybrid simulation part 1 (SIMULATED; GAIL_R_HYBRID_SIMULATION_PLAN_22NOV.md; 22 Nov 12:19-18:05)
Real inputs of the final run (small creators: 5,744 rows, 187 exposed); real estimate removed, known effect planted;
GAIL-R uniform attention, placebo penalty 30, window effects; 40 studies per size, creator bootstrap B = 100.
| planted | detected | mean estimate (log) | truth (log) |
|---|---|---|---|
| 0% | 0/40 | +0.071 | 0.000 |
| +10% | 0/40 | +0.088 | +0.095 |
| +20% | 0/40 | +0.160 | +0.182 |
| +30% | 1/40 | +0.222 | +0.262 |
| +40% | 4/40 | +0.275 | +0.336 |
| +60% | 13/40 | +0.398 | +0.470 |
Reading: no false alarm (0/40 at 0%); estimates rise with the planted effect and stay somewhat below it; at the real
number of small creators GAIL-R detects even a +60% effect in only a third of studies. Its non-significance on the real
data (+12.9%) is therefore expected at this sample size. Not a result about real spillover. Part 2 (more creators) follows.

## 12. Hybrid simulation part 2: more small creators (SIMULATED; GAIL_R_HYBRID_SAMPLE_SIZE_PLAN_22NOV.md; 22 Nov 18:07-20:30)
Real inputs of the final run; K x the 168 small creators drawn with replacement per study (each draw a separate creator);
10 studies per cell, creator bootstrap B = 50; detected = 95% interval above 0.
| creators per study | planted | detected | mean estimate (log) | truth (log) |
|---|---|---|---|---|
| 336 (2x) | +13% | 4/10 | +0.149 | +0.122 |
| 336 (2x) | +30% | 8/10 | +0.242 | +0.262 |
| 672 (4x) | +13% | 7/10 | +0.152 | +0.122 |
| 672 (4x) | +30% | 9/10 | +0.210 | +0.262 |
| 1,344 (8x) | +13% | 9/10 | +0.150 | +0.122 |
| 1,344 (8x) | +30% | 10/10 | +0.251 | +0.262 |
| 1,344 (8x) | 0% (false-alarm check) | 1/10 | +0.045 | 0.000 |
Reading: detection rises with the number of creators: +30% reliably (>= 80%) from 2x, +13% from about 8x (9/10).
Caveats, reported with the result: (1) a small upward lean of about +0.03 to +0.07 (also +0.071 at 0% in part 1), so
detection of small effects is somewhat helped by it; (2) the false-alarm check at 8x gave 1/10 (10%; with 10 studies
this is consistent with the nominal 5% but not proof of it); (3) more creators are resampled copies of the real ones,
which assumes new creators behave like them. Method validation only; not a result about real spillover.

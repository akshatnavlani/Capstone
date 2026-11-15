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

# Spillover re-run, 7 Nov 2026: results against the plan

Plan: SPILLOVER_PREREGISTRATION_6NOV.md (written 6 Nov 23:30 IST, addendum 7 Nov 15:15 IST, both before any
re-run). Log: exports/spillover_run_7nov.log (attempt 1, exports/spillover_run_7nov_attempt1.*, stopped on a dropped
database connection before any estimate; attempt 2 is the run reported). Checkpoint kept as
models/gail_checkpoint_7nov_run.pt; the app's models/gail_checkpoint.pt was restored to the 1 Nov file.

## What changed in the data (all chosen before the run, on identity or pre-set rules)
| | Before | After |
|---|---|---|
| Labelled sponsorship events (data/event_brand_labels.csv) | 92 | 2,905 (2,839 fitness/health) |
| Linked creators held (audit_collab_funnel.py) | 452 | 670 |
| Linked creators with a usable window | 92 | 187 |
| Pairs the pipeline uses (frequent_collaborator) | 84 pairs / 44 creators | 189 pairs / 133 creators |
| Canonical computable pairs (pair_count.py) | 4,426 (run 8) | 6,706 |
| Lift rows kept by the event rule | 3,870 of 4,426 (run 8) | 5,248 of 5,600 |
| Independent exposed observations | 23 / 10 creators (Eesha, 6 Nov) | 298 / 96 creators |

Settings: defaults (30-day windows, GAIL_EVENTS=fitness, GAIL_CREATORS=fitness, P2b on, aipw); no shared-brand
links (SHARED_BRAND_TARGETS unset). Only code change: a reconnect-and-retry wrapper on the engagement queries
(scripts/train_prod_model.py, _ResilientCursor), which changes no number.

## Primary result (pass mark: 95% interval excludes 0 AND placebo includes 0)
GAIL-R with placebo penalty, creator-level bootstrap B=200, 1,820 observations (298 exposed + 1,522 control) from
299 creators:
- effect on the 298 exposed observations: **-0.129, 95% CI [-0.253, +0.018]**
- collaborates_with slope (0% -> 100% neighbours sponsored): -0.167 [-0.316, +0.024]
- without the placebo penalty: -0.131 [-0.254, +0.018]

**Verdict: spillover NOT detected** (the interval includes 0). Bounded null: on the log scale a positive spillover
larger than +0.018 (about +1.8%) is ruled out; the estimate leans negative (about -12%) but is not established.

## Secondary numbers (reported, not the test)
- Matched DiD (no model): -0.198, SE 0.086, [-0.367, -0.028] over 245 exposed vs 1,522 controls in 161 windows.
- Category-matched DiD: -0.196, SE 0.090.
- Placebo (pre-trend) DiD: +0.112, SE 0.083, on 258 exposed with pre-period data. Exposed neighbours were rising
  before the event, so the plain DiD drop is partly a return to normal (mean reversion). This is why the plan names
  GAIL-R with the placebo check as the primary test and not the plain DiD.
- The co_occurs_with slope (-2.19, interval [-1.98, +1.92]) is unstable: its point lies outside its own bootstrap
  interval; do not quote it.

## Sensitivity (added 7 Nov 15:15 IST): without affiliate-heavy creators
Creators with > 25% of stored posts sponsored, excluded as measured creators: Anushka Sharma, Ankit Yadav (The
Complete Men), Varun dutt dubey, Yash Anand, Shivaji Fitness (Shivam Yadav), COREFITLAB, Rubal Dhankar.
Result (log exports/spillover_run_7nov_sensitivity.log): the same 298 exposed observations across 96 creators (these
creators are sponsors, and as neighbours they were already dropped by P2b); 1,510 controls (12 fewer).
- GAIL-R with placebo penalty: **-0.115, 95% CI [-0.253, +0.007]**: NOT detected, same verdict.
- collaborates_with slope: -0.148 [-0.334, +0.008].
- Matched DiD -0.196 [-0.365, -0.027]; placebo DiD +0.121 (SE 0.083).
The primary result does not depend on affiliate-heavy creators.

## Thesis wording (draft)
With 298 independent exposed observations across 96 Indian fitness and health creators, no positive spillover was
detected: the 95% interval for the effect of a collaborator's sponsorship on a linked creator's engagement is
[-25%, +2%], so boosts above about 2% are ruled out. The estimate leans negative, consistent with linked audiences
sharing attention rather than being lifted, but this is not statistically established.

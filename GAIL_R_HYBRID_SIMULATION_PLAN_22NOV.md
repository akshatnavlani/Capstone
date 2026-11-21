# Hybrid (semi-synthetic) simulation of GAIL-R on the final run's real data (plan fixed 22 Nov 2026, before any number)

Agreed with Shimona (22 Nov: "the hybrid one ... do that only"). This is METHOD VALIDATION and a POWER check, not a
result about real spillover. It is reported as simulated in every place it appears (her rule of 30 Oct: semi-synthetic
only, real graph and outcomes, effect planted, never mixed into real data or training).

## Inputs (real)
The GAIL-R inputs of the final run (GAIL_R_FINAL_SMALL_CREATORS_PLAN_17NOV.md settings: GAIL_TREATMENT=collab,
GAIL_FEATURED_ONLY=1, 7-day outcome, 30-day baseline, all event lists): the creator graph and features, the treatment
vectors and the observation rows, saved by re-running scripts/train_prod_model.py up to the GAIL-R step
(GAIL_SAVE_R_INPUTS; it stops there, writes no model). Database state of 22 Nov (a day newer than the final run).

## Planting
- Rows of small creators (< 100,000 subscribers), as in the final run's primary reading.
- Exposed rows = GAIL-R's own definition (a collaborating neighbour treated in the row's window, U[:, 0] > 0).
- First the real estimate is removed from exposed rows (y - att_real), so a planted effect of 0 is a true null; then a
  known effect d is added to exposed rows: d = log(1 + p) for p = 0%, +10%, +20%, +30%, +40%, +60%.
- Each simulated study resamples creators with replacement (new study, real noise), seed fixed.

## Estimator and reading
- GAIL-R as in ml/gail_r.py: fit_gail_r with uniform attention (as its bootstrap uses), placebo penalty 30, window
  effects on; creator-level cluster bootstrap, B = 100 per study; detected = 95% interval above 0.
- Number of studies per planted size: as many as fit in the time (target 40; the count is reported).
- Reported: per planted size, share of studies detected (p = 0% gives the false-alarm rate, target about 5%) and mean
  estimate vs truth. The size detected in at least 80% of studies is GAIL-R's detection threshold on this data.

## Rules
Run once; reported whatever it shows; never described as real spillover. Output models/gail_r_hybrid_sim_22nov.json.

# Hybrid simulation part 2: how many small creators GAIL-R needs (plan fixed 22 Nov 2026, ~17:00, before any number)

Agreed with Shimona (22 Nov: "I want GAIL to properly detect spillover as per the simulation"). Part 1
(GAIL_R_HYBRID_SIMULATION_PLAN_22NOV.md) keeps the real number of small creators (187 exposed rows): so far GAIL-R
estimates the planted size well (+10% -> +8.8%, +20% -> +16.0%, +30% -> +22.2%) with no false alarm at 0% (0/40), but
detects rarely (0, 0, 1 of 40), because its interval is wide at this sample size. Part 2 asks how its detection grows
with more small creators. SIMULATED; method validation and sample-size guidance only; never real spillover.

## Design (same inputs, estimator and rules as part 1; only the number of creators per simulated study changes)
- Each simulated study draws K x (number of small creators) creators with replacement from the real small creators,
  K = 2, 4, 8; drawn creators are relabelled as distinct creators (so the creator-level bootstrap treats them as
  separate creators, as new creators would be).
- Planted effects: +13% (the size of the real estimate) and +30%; the real estimate is first removed from exposed rows
  as in part 1. Also 0% at K = 8 (false-alarm check at the largest size).
- GAIL-R: fit_gail_r with uniform attention, placebo penalty 30, window effects; creator-level bootstrap over the drawn
  creators (each draw resampled as a unit, the same procedure as ml.gail_r.cluster_bootstrap), B = 50;
  detected = 95% interval above 0. 10 studies per (K, effect).
- Sizes chosen for time (fit time grows with K; about 4 hours in total), fixed before any number of part 2.

## Reading
Reported: detection share per (K, effect), mean estimate vs truth, false alarms at 0%. "Reliably detects" = at least
80% of studies. Run once; reported whatever it shows. Not a claim about real spillover. Output
models/gail_r_hybrid_sample_size_22nov.json.

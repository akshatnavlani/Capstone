# GAIL-R sponsorship spillover: one update run on the larger history (plan fixed 14 Nov 2026, 00:20, before the run)

Agreed with Shimona (13-14 Nov: "run everything that is required"). Written before any GAIL-R number on the new data exists.

## Why
The paper's real-data result (11 Nov 2026 run of scripts/train_prod_model.py: 305 exposed observations, effect -0.158,
95% CI [-0.296, +0.030], positive spillover above about 3% ruled out) used about 24 months of YouTube history. Since
12 Nov the older history (Nov 2022 - Nov 2024) is being added for all 381 in-scope channels, so more sponsorship events
and more neighbour windows become computable. More exposed observations give a narrower interval, whatever its centre.

## Run (once)
- When: after the Nov 2022 - Nov 2024 history is complete for the in-scope channels (the same condition as
  TAG_ENGAGEMENT_OLDER_PERIOD_PLAN_12NOV.md), expected 14-15 Nov 2026.
- Code and settings: scripts/train_prod_model.py as on 14 Nov 2026 with its defaults (GAIL_EVENTS=fitness,
  GAIL_CREATORS=fitness, GAIL_WINDOW_FE=1, GAIL_R_PLACEBO=30, GAIL_R_BOOT=200, seed 0). No setting is changed.
  Caveat stated in advance: the 11 Nov run's exact environment was not saved in the repository; the defaults are
  assumed to match it.
- The app's model files (models/gail_checkpoint.pt, feature_scaler.json, training_pair_ids.json) are backed up first
  and put back afterwards; the new checkpoint is kept as models/gail_checkpoint_update_14nov.pt and the printed report
  as models/gail_r_update_14nov.log.

## Reading (fixed now)
- Detected only if the 95% interval of the effect on exposed observations (placebo penalty 30) is above 0, as before.
- Otherwise the upper end of the interval is the new bound on positive spillover.
- Both runs (11 Nov and this update) are reported, with their observation counts. No further re-runs before 21 Nov.

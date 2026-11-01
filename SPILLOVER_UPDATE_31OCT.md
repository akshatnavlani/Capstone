# Spillover: what changed on 30-31 Oct 2026, and where it stands

For Eesha and Dr Tiwari's review. Everything below is in the repo (uncommitted until Shimona commits) and in the app (Analysis > S9, Dashboard "Spillover what-if").

## Result (honest version)
- **No spillover is detectable.** GAIL-R estimate on the exposed: **-0.16, 95% interval -0.40 to +0.40**. Matched estimate -0.09 (SE 0.11). 10 seeds: mean -0.05, seeds -0.16 to +0.09. Held-out creators: the effect term does not help (median gain -3.2%, wrong-window null -1.8%).
- The test is much sharper than before: **60 exposed observations from 17 creators (was 19 from 8)**, so effects above about **1.5x engagement** are ruled out (it was 2.7x). Small effects are neither shown nor ruled out.
- Caution: many of the 60 exposures come from **@mention links**, which are weaker evidence than co-author posts; any result is "mention-linked exposure".

## What was done
1. **More real exposed cases.** Mined @mentions in titles, descriptions and captions of our 121 sponsoring creators (1,527 unknown handles); added 14 + 5 real creators (fitness, nutrition, health) with their YouTube history (8,262 videos), 3 alias links (Ranveer Allahbadia, Elvish Yadav, Karan Aujla), and collected Instagram for 7 creators that blocked training pairs. `scripts/ingestion/add_collaborator_creators.py`, shortlist in `models/collaborator_candidates_31oct.json`.
2. **Instagram job targets what matters**: alternates creators that block pairs and uncollected both-platform creators, ranked by recent YouTube uploads; the count step no longer wastes loads (`instagram_daily.py`, `instagram_backfill_counts.py`).
3. **Four extra tests, none detects an effect**: hourly views around sponsored videos (`scripts/run_spillover_event_study.py`; only 6 usable pairs, too few yet), the same on timed comments over the long history (108 pairs, 21 creators; random-pair false-alarm control clean), label-noise sensitivity (`scripts/run_label_noise_sensitivity.py`: even 30% missed labels keep the upper end below 1.2x), and a real-case comparison (`scripts/find_spillover_cases.py`: 10% of exposed cases rise above +0.5 against 14% of unexposed; the best cases are the best of many).
4. **Simulation, labelled simulated, never mixed into real results**: cases needed for 80% detection (about 20 exposed for a 1.65x effect, 100+ for 1.3x); GAIL-R accuracy as exposed creators grow (clean error 0.14, 0.12, 0.08 at 19, 40, 80; with a pre-existing trend the error stays 0.23-0.25 without the placebo penalty, 0.13 at 80 with it; 5 repeats only).
5. **Fusion fix**: a branch that knows nothing about a creator (no graph link, no scored comments, no feature evidence) is left out and the others rescaled (`backend/app/fusion.py effective_weights`). Priors 0.2/0.4/0.4 unchanged; fitting to the buying-comment proxy was tested and NOT adopted (it would switch off spillover and sentiment).
6. **Spillover what-if tool** (`GET /scenario/spillover`, `backend/app/spillover_scenario.py`, dashboard switch): real graph + real sponsorships of the last 30 days + an assumed strength; never changes a score. Tests: backend 135 pass.

## Files to look at
`models/gail_real_results.json` (run table), `models/power_analysis.json`, `models/gail_r_multiseed.json`, `models/gail_r_holdout.json`, `models/label_noise_sensitivity.json`, `models/spillover_event_study.json`, `models/spillover_cases.json`, `models/semisynth_scale.json`, `CAPSTONE_NEXT_STEPS.md` (the 31 OCT paragraphs), offline package `exports/gpu_package_31oct.zip` (inputs, code and README; no secrets).

## How to rerun
`python scripts/refresh_analyses.py` (pairs, ad fatigue, long lag, growth-reading lag, spillover event study, label-noise table, promotion, dashboard). The readings version of the event study becomes usable as sponsored events and readings accumulate (the 2-hourly job follows every channel in the database, including the 19 added creators). Retraining needs the scratch copy of train_prod_model.py with the DB-reconnect and feature-cache patches (see CAPSTONE_NEXT_STEPS.md 31 OCT).

## Open for Eesha
- E4 and E5 are now built (new file `ml/gail_r_ext.py`, tests `tests/test_gail_r_ext.py`, runner `scripts/run_e4_e5.py`, results `models/e4_e5_results.json`; `ml/gail_r.py` untouched, needs the `merge-eesha-ml` merge to run). Simulated results, 6 replicates:
  - E4: supervising attention with the causal (orthogonalised) loss recovers per-creator effects far better than plain outcome error (error 0.06 vs 0.39 in a clean world; 0.32 vs 0.50 with a pre-existing trend). But learned attention does no better than uniform neighbour weights (0.0615 vs 0.0619), so what protects the estimate is the causal loss, not the attention itself. Say it that way.
  - E5: MC-SIMEX for missed sponsor labels cuts the error at 70% recall from 0.107 to 0.026 and at 50% from 0.158 to 0.063 (no gain at 90%). It needs the recall as an input; ours is unknown.
  - E5 on real data: correcting for recalls 0.9 and 0.8 leaves the estimate about zero or slightly negative (average effect -0.02 to -0.03). At recall 0.7 or lower the relation slopes become unstable (the co-occurrence slope flips sign), so do not quote those.
- A GPU run with 20+ seeds and a 1,000-draw bootstrap on `gail_r_inputs_run7.pt`.
- Merge of `merge-eesha-ml` into Shimona's branch (blocks the fusion calibration on the new checkpoint).

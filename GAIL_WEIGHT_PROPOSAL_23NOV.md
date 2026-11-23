# Proposal: give GAIL's network score a weight in the final score (23 Nov 2026)

**Status: prepared, switched OFF. Needs Shimona's and Eesha's agreement before it is turned on.**

## Today (agreed 7 Nov 2026)
Final score = 100 x (0.4 value for money + 0.3 audience mood + 0.3 content match), minus 10 if mood < 0.3
(`backend/app/fusion.py: compute_value_score`). GAIL's network score (`score_breakdown.spillover_score`, the creator's
percentile among graph-connected creators) is computed for every creator and shown alongside, with weight 0.
The 7 Nov note says this was "temporary, until spillover is detectable".

## What changed since 7 Nov
- Spillover through collaborations is detected by pre-registered tests: tagged creators +0.095 [+0.005, +0.185]
  (about +10%, 7 days, 291 events); small creators featured in joint videos +0.277 [+0.113, +0.529] (about +32%,
  14 days, 67 events). Both are secondary tests of their plans (SPILLOVER_RESULTS_OVERALL_22NOV.md).
- GAIL-R's own final estimate is positive but not significant (small creators +0.129 [-0.100, +0.378]); the power
  analysis and hybrid simulation show this is a sample-size limit (GAIL_R_RESULTS_15NOV.md sections 9-12).

## The proposal
Set `FUSION_WEIGHT_GAIL_IN_VALUE=0.15` in `.env`. For creators GAIL actually scored (basis `trained` or `inferred`):
final = 100 x (0.85 x (0.4 value + 0.3 mood + 0.3 fit) + 0.15 x GAIL), i.e. 34% value, 25.5% mood, 25.5% content,
15% GAIL. Creators without a GAIL score (no links, placeholder) keep the 7 Nov formula unchanged.
The app (Live Match bars and texts) follows the weights the backend returns, so nothing else needs editing.

## For and against
- For: the project's central model then moves the ranking, and collaboration spillover is now detected on real data.
- Against: GAIL-R's estimate is not yet significant, and GAIL's network score is a position (who is well connected),
  not a measured gain for that creator. A panel may ask why a non-significant branch is in the score.
- Middle ground: keep 0 and present GAIL as shown alongside (what the app does now), or use a small weight such as 0.10.

## Checks
- `backend/tests/test_fusion_value.py::test_gail_weight_switch`: weight 0 (or no GAIL score) gives exactly the 7 Nov
  score; weight g gives (1 - g) x old + g x GAIL.
- Before turning it on: run one brief with 0 and with 0.15 and compare the top 10 (how many creators move).

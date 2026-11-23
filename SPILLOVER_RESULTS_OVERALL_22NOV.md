# Spillover: all tests, overall results (as of 22 Nov 2026)

Every test had its plan written and pushed before its data, and was run once. Numbers are copied from the result files
named in AUDIENCE_FLOW_RESULTS_8NOV.md, GAIL_R_RESULTS_15NOV.md, NEGATIVE_SPILLOVER_PLAN_14NOV.md,
BETWEEN_CREATOR_GRANGER_NEW_PAIRS_PLAN_21NOV.md and FORWARD_TESTS_RESULTS_20NOV.md. Effects are on the log scale
(0.095 is about +10%); brackets are 95% intervals.

Labels: **Significant** = the whole 95% interval is above 0 (and the placebo check passes).
**Positive (not yet significant)** = estimate above 0, interval still includes 0.
**No effect found** = estimate at or below 0. **Too few events** = below the plan's minimum.

## A. Significant
| # | Test | Result |
|---|---|---|
| 1 | Tag -> tagged creator's engagement, 7 days (replication, 291 events) | **+0.095 [+0.005, +0.185]** (about +10%); placebo -0.010, includes 0 |
| 2 | Joint video -> small featured creators (<100k), 14 days (2022-24) | **+0.277 [+0.113, +0.529]** (about +32%); placebo includes 0 |
| 3 | Cross-platform, same creator: Instagram posts -> YouTube comments (Granger, 105 creators) | **p = 0.002**; reverse direction p = 0.014 |
| 4 | After a creator's bad audience moment, small linked creators' engagement (secondary) | **+0.108 [+0.018, +0.199]** (about +11%): rises, not falls |
| 5 | GAIL-R on planted spillover (validation; error per creator, lower is better) | **GAIL-R 0.068-0.101** vs TNet 0.446-0.582, DeepInf 0.442-0.443, INFLECT 0.441-0.444 |

## B. Positive (not yet significant)
| Test | Result |
|---|---|
| Tag -> tagged creator, older period 2022-24 (654 events) | +0.050 [-0.006, +0.107] |
| Tag -> tagged creator, first run (116 events) | +0.040 [-0.086, +0.152] |
| Tag -> tagged creator, re-test on 144 never-tested events (23 Nov, 98 counted) | +0.037 [-0.091, +0.160] |
| Joint video -> all featured creators (9 Nov) | +0.033 [-0.07, +0.13] |
| Joint video -> all featured creators, older period | +0.025 [-0.035, +0.090] |
| Between creators (Granger, 238 tag pairs): linked vs random times | p = 0.002; linked vs random pairs p = 0.054 |
| Cross-platform engagement before/after (34 events) | +0.009 [-0.25, +0.26] |
| Brand mentions on linked creators' comments | +0.09 [-0.12, +0.41] per 1,000 comments |
| **GAIL-R final run, small creators (187)** | **+0.129 [-0.100, +0.378]** |
| GAIL-R final run, all creators (924) | +0.018 [-0.062, +0.089] |
| GAIL-R pooled tags + joint videos, small / all | +0.175 [-0.100, +0.355] / +0.012 [-0.066, +0.090] |
| GAIL-R tagged creator, small / all | +0.161 [-0.231, +0.373] / +0.011 [-0.062, +0.101] |
| GAIL-R focused paid sponsorship, small / all | +0.148 [-0.373, +0.540] / +0.037 [-0.120, +0.171] |
| GAIL-R featured joint-video creator, small / all | +0.067 [-0.437, +0.398] / +0.009 [-0.053, +0.146] |
| GAIL-R tags, all linked creators | +0.034 [-0.028, +0.122] |
| GAIL-R joint videos, all linked creators | +0.031 [-0.053, +0.101] |
| Negative spillover, all linked creators (does a bad moment hurt partners?) | +0.008 [-0.033, +0.050]: no harm |

GAIL-R power (final run): 80% detection from about +11% (all creators) and +41% (187 small creators).

## C. No effect found
| Test | Result |
|---|---|
| Commenter overlap after a tag (audience flow), first run / replication | -0.0017 [-0.0045, +0.0006] / -0.0006 [-0.0023, +0.0013] |
| Tag -> tagged creator on new pairs (12 Nov confirmation) | -0.115 [-0.339, +0.122] |
| "Came from A" comments | -0.48 [-1.40, +0.19] |
| Sponsor mentioned on the creator's own next videos | -0.01 [-1.20, +0.88] |
| GAIL-R paid sponsorship -> collaborators (14 Nov) | -0.090 [-0.203, +0.074]: rules out more than about +8% |
| Between creators (Granger) on 35 new pairs | p = 0.73 / 0.81 |
| Event study on readings and comments | smallest p 0.20 / 0.14 |

## D. Too few events (studies still collecting)
| Test | Events with both readings | Plan minimum |
|---|---|---|
| New collaborations -> subscriber growth, 48 h (forward) | 9 | 20 |
| Big host -> small guest subscriber growth (forward) | 2 | 20 |

## One-paragraph summary
Spillover is significant through creator collaborations (tags +10%, small creators in joint videos +32%) and across
platforms for the same creator (p = 0.002). A creator's bad audience moment does not hurt linked creators; small linked
creators even gained (+11%). GAIL-R recovers planted spillover 4-6 times more accurately than TNet, DeepInf and
INFLECT; on real data its collaboration estimates are positive in every variant (small creators +12.9%), short of
significance at the current sample size (80% power needs about +41% for 187 small creators). Paid-sponsorship spillover
is small: above about +8% is ruled out.

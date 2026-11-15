# GAIL-R, paid sponsorship spillover where it is most likely: small collaborators, 7 days, strong evidence
# (plan fixed 15 Nov 2026, 22:15, before any code or run for this question)

Agreed with Shimona (15 Nov: "how can we prove this ... do it"). The full update (GAIL_R_RESULTS_15NOV.md: 555 exposed,
-0.090 [-0.203, +0.074]) found no sponsorship spillover onto collaborators over 30 days. The collaboration tests found
spillover only for small creators and within days (joint video, B under 100k, +0.277). This asks the same question of
paid sponsorships where an effect, if any, should be largest. Written after seeing the full-update result (stated here),
before any number of this variant exists.

## Changes from the update run (everything else identical: GAIL_TREATMENT=sponsorship, fitness event rule, window
## effects, attention shrinkage, placebo penalty 30, creator bootstrap B = 200, seed 0)
1. Outcome window 7 days after the event (baseline 30 days before, GAIL_BASELINE_DAYS=30), via a new switch
   GAIL_OUTCOME_DAYS=7 (default 30 unchanged).
2. Strong evidence only, via a new switch GAIL_STRONG_EVENTS=1: YouTube sponsorship_evidence in (spoken,
   creator_comment, disclosure_tag); Instagram has_paid_partnership_label or sponsorship_evidence in (official_label,
   disclosure_tag). brand_and_code and brand_mention events are left out (2,745 + 298 YouTube, 37 + 19 Instagram).
3. Primary reading on collaborators under 100,000 subscribers (GAIL_R_SMALL_B=1); the all-collaborator estimate is
   printed alongside as secondary.

## Reading (fixed now)
- Detected only if the 95% interval of the effect on exposed small-collaborator observations (placebo penalty 30) is
  above 0, with at least 20 exposed observations; fewer than 20 = printed, not a result.
- Run once, after the joint-video, tag and negative-spillover runs of 15 Nov. Multiple testing: one more test after
  about twenty; a pass is "suggestive, needs confirmation". A null is reported as "no sponsorship spillover even where it
  is most likely".

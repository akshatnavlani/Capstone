"""Fusion Layer: combines GAIL spillover score, Temporal branch
sentiment/risk score, and creator feature score into a final 0-100 score
with confidence bounds and risk adjustment (PROJECT_PLAN.md Section 4).

final_score = w1*spillover + w2*sentiment_risk + w3*creator_feature

Weights: w1=0.4 w2=0.3 w3=0.3 are still placeholder/un-calibrated —
only w1 (spillover via GAIL checkpoint c6488a6) is now real; w2
sentiment_risk_score remains 0.5 placeholder until Temporal branch lands
(CAPSTONE_NEXT_STEPS.md:822, 778-795). Do not recalibrate w1/w2/w3 as if
all are real; w2 has zero variance modeled and should stay 0.5.

Confidence heuristic (honest small-N, N≈10 effective labeled nodes):
  spillover ~ prediction-interval : hw = t_{0.975,df} * residual_std * sqrt(1+1/N)
  where residual_std = sqrt(mse_trained), df=N-2, t=2.306 at N=10 (table in
  app/gail/inference.py). Inferred multiplies base_hw *1.6x, min 0.25.
  Placeholder/isolated use same wide hw (0.25 min). This is the ONLY variance
  modeled today — w2/w3 are still fixed, so final CI = hw*100*w1, clamped
  [0,100]. Even 'trained' CI spans ~±15pts on 0-100; inferred/placeholder
  ±25pts, reflecting propensity saturates 1.000 (CAPSTONE_NEXT_STEPS.md:795)
  and N=10 collapse (787). See also API_CONTRACTS.md Fusion / Confidence.
"""

from app.config import settings
from app.schemas import ScoreBreakdown

# Fixed placeholder confidence margin (± points on the 0-100 scale) until
# real bootstrapped/ensemble variance from the GAIL branch is available.
# Kept as fallback when no GAIL half-width is supplied (e.g. legacy callers).
PLACEHOLDER_CONFIDENCE_MARGIN = 8.0

# Below this sentiment/risk threshold, apply a flat risk-adjustment penalty.
# Placeholder heuristic pending the real sentiment-propagation risk model.
RISK_THRESHOLD = 0.3
RISK_PENALTY_POINTS = 10.0


def compute_fusion_score(
    spillover_score: float,
    sentiment_risk_score: float,
    creator_feature_score: float,
    spillover_half_width: float | None = None,
    spillover_basis: str | None = None,
) -> tuple[float, float, float, float, ScoreBreakdown]:
    """Returns (final_score, confidence_low, confidence_high, risk_adjustment, breakdown).

    Inputs are expected in [0, 1]; final_score is on a 0-100 scale.
    """
    w1 = settings.fusion_weight_spillover
    w2 = settings.fusion_weight_sentiment_risk
    w3 = settings.fusion_weight_creator_feature

    raw_score = w1 * spillover_score + w2 * sentiment_risk_score + w3 * creator_feature_score
    base_score = raw_score * 100

    risk_adjustment = -RISK_PENALTY_POINTS if sentiment_risk_score < RISK_THRESHOLD else 0.0
    final_score = max(0.0, min(100.0, base_score + risk_adjustment))

    # Honest CI: if GAIL half-width (0-1 scale) is supplied, scale by w1*100;
    # otherwise fallback to fixed placeholder ±8 (legacy callers/tests).
    if spillover_half_width is not None:
        margin = spillover_half_width * 100 * w1
        confidence_low = max(0.0, final_score - margin)
        confidence_high = min(100.0, final_score + margin)
    else:
        confidence_low = max(0.0, final_score - PLACEHOLDER_CONFIDENCE_MARGIN)
        confidence_high = min(100.0, final_score + PLACEHOLDER_CONFIDENCE_MARGIN)

    breakdown = ScoreBreakdown(
        spillover_score=spillover_score,
        sentiment_risk_score=sentiment_risk_score,
        creator_feature_score=creator_feature_score,
        weight_spillover=w1,
        weight_sentiment_risk=w2,
        weight_creator_feature=w3,
    )

    return final_score, confidence_low, confidence_high, risk_adjustment, breakdown

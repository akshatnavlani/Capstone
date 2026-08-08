"""Fusion Layer: combines GAIL spillover score, Temporal branch
sentiment/risk score, and creator feature score into a final 0-100 score
with confidence bounds and risk adjustment (PROJECT_PLAN.md Section 4).

final_score = w1*spillover + w2*sentiment_risk + w3*creator_feature

This is currently a STUB: weights are hardcoded defaults (not yet
calibrated against held-out historical outcomes), and confidence bounds
are a fixed placeholder margin rather than bootstrapped/ensemble variance
from the GNN. Replace both once ML-Core (Track B) ships real outputs.
"""

from app.config import settings
from app.schemas import ScoreBreakdown

# Fixed placeholder confidence margin (± points on the 0-100 scale) until
# real bootstrapped/ensemble variance from the GAIL branch is available.
PLACEHOLDER_CONFIDENCE_MARGIN = 8.0

# Below this sentiment/risk threshold, apply a flat risk-adjustment penalty.
# Placeholder heuristic pending the real sentiment-propagation risk model.
RISK_THRESHOLD = 0.3
RISK_PENALTY_POINTS = 10.0


def compute_fusion_score(
    spillover_score: float,
    sentiment_risk_score: float,
    creator_feature_score: float,
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

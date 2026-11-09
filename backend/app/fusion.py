"""Fusion Layer: combines GAIL spillover score, Temporal branch
sentiment/risk score, and creator feature score into a final 0-100 score
with confidence bounds and risk adjustment (PROJECT_PLAN.md Section 4).

final_score = w1*spillover + w2*sentiment_risk + w3*creator_feature

All three inputs are on a 0-1 scale. Spillover is the creator's percentile among
graph-connected creators (app/spillover.py `spillover_unit`), not the raw
engagement lift, which is unbounded (-1 to +23) and used to saturate the score
at 100. Sentiment (app/temporal.py) and feature (app/creator_features.py) are 0-1
already.

Weights w1=0.0 w2=0.5 w3=0.5 (spillover taken out of the score on 1 Nov 2026, from 0.2 / 0.4 / 0.4 on 30 Oct and 0.4 / 0.3 / 0.3 before; see config.py) are documented priors, not fitted values: the only
labelled outcome is the 10-creator engagement lift GAIL was trained on, and
sentiment and feature have no outcome to fit against. scripts/calibrate_fusion.py
measures how much the ranking moves if the weights change.

Evidence-weighted (30 Oct 2026): a branch with no information for this creator (no graph link, no scored comments, no feature evidence) is left out and the other
weights are rescaled (`effective_weights`), so a creator is never credited with a neutral score that no data supports. The breakdown reports the weights actually used.

Confidence interval (PendingWork S3: all three branches, not just spillover).
Each branch gets a 95% half-width on its own 0-1 scale and they are combined in
quadrature, assuming the branch errors are independent:

  margin = 100 * sqrt((w1*hw1)^2 + (w2*hw2)^2 + (w3*hw3)^2)

  hw1 spillover : GAIL prediction interval mapped through the percentile
                  transform (small N=10 -> wide); no graph signal -> 0.475
  hw2 sentiment : 1.96 * 0.5 / sqrt(n_comments + 20); 0.27 with no scored comments
  hw3 feature   : 0.475 with no evidence, 0.43 when scored (see the constants)

The interval is clamped to [0, 100]. See also API_CONTRACTS.md Fusion / Confidence.
"""

import math

from app.config import settings
from app.schemas import ScoreBreakdown

# Fallback confidence margin (± points on the 0-100 scale) when the caller gives
# no spillover half-width at all (legacy callers/tests).
PLACEHOLDER_CONFIDENCE_MARGIN = 8.0

# Below this sentiment/risk threshold, apply a flat risk-adjustment penalty.
RISK_THRESHOLD = 0.3
RISK_PENALTY_POINTS = 10.0

# 95% half-width of a uniform 0-1 rank: all we can say when nothing is known.
UNIFORM_HALF_WIDTH = 0.475

# Sentiment: a safety score lies in [0, 1], so one comment's sd is at most 0.5;
# the mean is shrunk toward 0.5 with strength 20 (ml/temporal/sentiment.py), so
# the posterior sd is bounded by 0.5 / sqrt(n + 20). Conservative on purpose.
SENTIMENT_SD_BOUND = 0.5
SENTIMENT_PRIOR_STRENGTH = 20
# No scored comments: 1.96 * the spread of safety across the 149 scored creators (0.136).
SENTIMENT_NO_DATA_HALF_WIDTH = 0.27

# Feature: S2 measured the text-relevance method at AUC 0.85 (fitness brief) and
# 0.57 (cricket brief), mean 0.71. AUC 0.71 is a rank correlation of 2*0.71-1 = 0.42,
# which leaves sqrt(1-0.42^2) = 0.91 of a uniform rank's spread unexplained.
FEATURE_RANK_CORRELATION = 0.42
FEATURE_SCORED_HALF_WIDTH = UNIFORM_HALF_WIDTH * math.sqrt(1 - FEATURE_RANK_CORRELATION**2)
FEATURE_NEUTRAL_HALF_WIDTH = UNIFORM_HALF_WIDTH


def sentiment_uncertainty(n_comments: int | None) -> float:
    """95% half-width (0-1 scale) of a creator's sentiment/risk score."""
    if not n_comments:
        return SENTIMENT_NO_DATA_HALF_WIDTH
    return 1.96 * SENTIMENT_SD_BOUND / math.sqrt(n_comments + SENTIMENT_PRIOR_STRENGTH)


def feature_uncertainty(basis: str | None) -> float:
    """95% half-width (0-1 scale) of the creator feature score; `basis` is the
    "scored"/"neutral" value from app/creator_features.py (None = not computed)."""
    return FEATURE_SCORED_HALF_WIDTH if basis == "scored" else FEATURE_NEUTRAL_HALF_WIDTH


def effective_weights(
    spillover_basis: str | None = None,
    sentiment_half_width: float | None = None,
    feature_half_width: float | None = None,
) -> tuple[float, float, float]:
    """The weights actually used for one creator (30 Oct 2026).

    A branch that knows nothing about this creator is left out and the other weights are rescaled to sum to the same total. Before, such a branch contributed a
    neutral 0.5 (worth 10 points at weight 0.2) to every creator that had no information, as if it were a real signal; creators with and without network
    information were then scored on different footing. Uninformative means: spillover basis "isolated" or "placeholder" (no link in the graph, so the score is the
    neutral default); sentiment with no scored comments; feature with no CLIP/BERT evidence. Callers that do not pass a basis or a half-width (legacy callers,
    tests) keep the plain configured weights. If every branch is uninformative the configured weights are kept.
    """
    base = (settings.fusion_weight_spillover, settings.fusion_weight_sentiment_risk, settings.fusion_weight_creator_feature)
    informative = (
        spillover_basis not in ("isolated", "placeholder"),
        sentiment_half_width is None or not math.isclose(sentiment_half_width, SENTIMENT_NO_DATA_HALF_WIDTH),
        feature_half_width is None or not math.isclose(feature_half_width, FEATURE_NEUTRAL_HALF_WIDTH),
    )
    kept = sum(w for w, ok in zip(base, informative) if ok)
    if not any(informative) or kept <= 0:
        return base
    scale = sum(base) / kept
    return tuple(w * scale if ok else 0.0 for w, ok in zip(base, informative))


def compute_fusion_score(
    spillover_score: float,
    sentiment_risk_score: float,
    creator_feature_score: float,
    spillover_half_width: float | None = None,
    spillover_basis: str | None = None,
    sentiment_half_width: float | None = None,
    feature_half_width: float | None = None,
) -> tuple[float, float, float, float, ScoreBreakdown]:
    """Returns (final_score, confidence_low, confidence_high, risk_adjustment, breakdown).

    Inputs are expected in [0, 1]; final_score is on a 0-100 scale. The half-widths
    are 95% half-widths on the same 0-1 scale as their score; a half-width that is
    not given contributes no uncertainty (legacy callers pass only spillover's).
    """
    w1, w2, w3 = effective_weights(spillover_basis, sentiment_half_width, feature_half_width)

    raw_score = w1 * spillover_score + w2 * sentiment_risk_score + w3 * creator_feature_score
    base_score = raw_score * 100

    risk_adjustment = -RISK_PENALTY_POINTS if sentiment_risk_score < RISK_THRESHOLD else 0.0
    final_score = max(0.0, min(100.0, base_score + risk_adjustment))

    if spillover_half_width is not None:
        margin = 100 * math.sqrt(
            (w1 * spillover_half_width) ** 2
            + (w2 * (sentiment_half_width or 0.0)) ** 2
            + (w3 * (feature_half_width or 0.0)) ** 2
        )
    else:
        margin = PLACEHOLDER_CONFIDENCE_MARGIN
    confidence_low = max(0.0, final_score - margin)
    confidence_high = min(100.0, final_score + margin)

    breakdown = ScoreBreakdown(
        spillover_score=spillover_score,
        sentiment_risk_score=sentiment_risk_score,
        creator_feature_score=creator_feature_score,
        weight_spillover=w1,
        weight_sentiment_risk=w2,
        weight_creator_feature=w3,
    )

    return final_score, confidence_low, confidence_high, risk_adjustment, breakdown


# Final score with value for money (agreed with Eesha, 7 Nov 2026; temporary, until spillover is detectable):
# 100 x (0.4 x value + 0.3 x mood + 0.3 x fit), minus 10 if mood < 0.3; budget stays a filter (routers/influencers.py).
# value = percentile (0-1) of engagement per Rs 1,000 among costed creators on the same platform (models/creator_value.csv).
VALUE_WEIGHTS = (0.4, 0.3, 0.3)


def compute_value_score(value_pct: float, sentiment_risk_score: float, creator_feature_score: float,
                        old_margin: float) -> tuple[float, float, float, float]:
    """(final_score, confidence_low, confidence_high, risk_adjustment). The value percentile carries no stated
    uncertainty, so the mood/fit margin is scaled by their combined weight (0.6)."""
    wv, wm, wf = VALUE_WEIGHTS
    risk_adjustment = -RISK_PENALTY_POINTS if sentiment_risk_score < RISK_THRESHOLD else 0.0
    final = max(0.0, min(100.0, 100 * (wv * value_pct + wm * sentiment_risk_score + wf * creator_feature_score) + risk_adjustment))
    margin = old_margin * (wm + wf)
    return final, max(0.0, final - margin), min(100.0, final + margin), risk_adjustment

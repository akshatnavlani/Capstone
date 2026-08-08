"""Brand-input -> ranked influencer list endpoint (PROJECT_PLAN.md Section 5,
recommendation engine).

Real ranking still depends on ML-Core's GAIL/Temporal outputs feeding the
Fusion Layer -- until then, `final_score` is either a real stored
FusionScore or a placeholder 0.5/0.5/0.5 fusion computation, and ordering
among eligible candidates is always by `final_score` descending.

What changed 2026-08-09 (was previously a no-op stub, see API_CONTRACTS.md):
- budget: hard filter via `estimated_cost` (a placeholder followers/subscribers
  * flat-rate heuristic -- no real rate-card data exists yet). Candidates with
  unknown reach data aren't excluded (can't compute a cost for them).
- target_region / target_demographic: soft filters. A creator is excluded
  only if we HAVE text signal for them (youtube_channels.country/description,
  instagram_profiles.bio) and it does NOT match. Creators with no signal data
  at all are kept -- with Weeks 3-4 scraping still ramping up, most creators
  won't have this data yet, and a hard requirement would return empty result
  sets for almost every query.
- product_category and platform_preference are still accepted/echoed only,
  not filtered on -- out of scope for this pass, flagged as still-open below.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.fusion import compute_fusion_score
from app.models import Creator, FusionScore, InstagramProfile, YouTubeChannel
from app.schemas import (
    BrandRecommendationRequest,
    BrandRecommendationResponse,
    InfluencerRecommendation,
    ScoreBreakdown,
)

router = APIRouter(tags=["recommendations"])

# Placeholder cost heuristic: no real rate-card/pricing data exists yet.
# INR per follower/subscriber, deliberately crude -- revisit once real
# campaign cost data is available (see PROJECT_PLAN.md Section 5's ROI note:
# "ROI" here means engagement-per-rupee, not sales/conversion).
COST_PER_FOLLOWER_INR = 0.5

_MOCK_CREATORS = [
    Creator(creator_id=uuid.uuid5(uuid.NAMESPACE_DNS, "mock-fitwithpriya"), name="FitWithPriya",
            category="fitness_influencer", youtube_handle="@FitWithPriya", instagram_handle="@fitwithpriya"),
    Creator(creator_id=uuid.uuid5(uuid.NAMESPACE_DNS, "mock-gymbro"), name="GymBro",
            category="fitness_influencer", youtube_handle="@GymBro", instagram_handle="@gymbro"),
    Creator(creator_id=uuid.uuid5(uuid.NAMESPACE_DNS, "mock-yogaguru"), name="YogaGuru",
            category="lifestyle_influencer", instagram_handle="@yogaguru", reddit_handles=["u/yogaguru"]),
]


def _text_matches(query: str | None, texts: list[str | None]) -> bool:
    if not query:
        return False
    q = query.lower()
    return any(t and q in t.lower() for t in texts)


def _to_recommendation(
    creator: Creator,
    score: FusionScore | None,
    youtube_channel: YouTubeChannel | None,
    instagram_profile: InstagramProfile | None,
) -> InfluencerRecommendation:
    if score is not None:
        breakdown = ScoreBreakdown(
            spillover_score=score.spillover_score,
            sentiment_risk_score=score.sentiment_risk_score,
            creator_feature_score=score.creator_feature_score,
            weight_spillover=settings.fusion_weight_spillover,
            weight_sentiment_risk=settings.fusion_weight_sentiment_risk,
            weight_creator_feature=settings.fusion_weight_creator_feature,
        )
        final_score, confidence_low, confidence_high = score.final_score, score.confidence_low, score.confidence_high
    else:
        # No real score yet: placeholder inputs pending ML-Core output.
        final_score, confidence_low, confidence_high, _risk_adj, breakdown = compute_fusion_score(0.5, 0.5, 0.5)

    reach = max((youtube_channel.subscriber_count if youtube_channel else 0) or 0,
                (instagram_profile.follower_count if instagram_profile else 0) or 0)

    return InfluencerRecommendation(
        creator_id=creator.creator_id,
        name=creator.name,
        category=creator.category,
        youtube_handle=creator.youtube_handle,
        instagram_handle=creator.instagram_handle,
        reddit_handles=creator.reddit_handles,
        final_score=final_score,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        estimated_reach=reach or None,
        estimated_cost=(reach * COST_PER_FOLLOWER_INR) if reach else None,
        score_breakdown=breakdown,
    )


@router.post("/recommendations", response_model=BrandRecommendationResponse)
def get_recommendations(
    request: BrandRecommendationRequest, session: Session = Depends(get_session)
) -> BrandRecommendationResponse:
    creators = session.exec(select(Creator).limit(1000)).all()
    using_mock_creators = False

    if not creators:
        creators = _MOCK_CREATORS
        using_mock_creators = True

    creator_ids = [c.creator_id for c in creators]
    youtube_channels = {
        yc.creator_id: yc
        for yc in session.exec(select(YouTubeChannel).where(YouTubeChannel.creator_id.in_(creator_ids))).all()
    } if not using_mock_creators and creator_ids else {}
    instagram_profiles = {
        ip.creator_id: ip
        for ip in session.exec(select(InstagramProfile).where(InstagramProfile.creator_id.in_(creator_ids))).all()
    } if not using_mock_creators and creator_ids else {}

    any_score_missing = False

    eligible: list[InfluencerRecommendation] = []
    for creator in creators:
        youtube_channel = youtube_channels.get(creator.creator_id)
        instagram_profile = instagram_profiles.get(creator.creator_id)

        # --- budget filter (hard, only when cost is computable) ---
        reach = max((youtube_channel.subscriber_count if youtube_channel else 0) or 0,
                    (instagram_profile.follower_count if instagram_profile else 0) or 0)
        estimated_cost = reach * COST_PER_FOLLOWER_INR if reach else None
        if estimated_cost is not None and estimated_cost > request.budget:
            continue

        # --- region-proxy filter (soft: only exclude on a confirmed mismatch) ---
        region_signals = [
            youtube_channel.country if youtube_channel else None,
            youtube_channel.description if youtube_channel else None,
            instagram_profile.bio if instagram_profile else None,
        ]
        has_region_signal = any(region_signals)
        if request.target_region and has_region_signal and not _text_matches(request.target_region, region_signals):
            continue

        # --- demographic-proxy filter (soft, same policy) ---
        demographic_signals = [
            instagram_profile.bio if instagram_profile else None,
            youtube_channel.description if youtube_channel else None,
        ]
        has_demographic_signal = any(demographic_signals)
        if request.target_demographic and has_demographic_signal and not _text_matches(
            request.target_demographic, demographic_signals
        ):
            continue

        score = None
        if not using_mock_creators:
            # Looked up per-creator regardless of any_score_missing from a prior
            # iteration -- a bug in the Weeks 1-2 version gated this on a single
            # shared flag, so one creator lacking a score silently stopped real
            # scores from being fetched for every creator after it in the loop.
            # Found via adversarial self-check on 2026-08-09.
            score = session.exec(
                select(FusionScore)
                .where(FusionScore.creator_id == creator.creator_id)
                .order_by(FusionScore.computed_at.desc())
            ).first()
            if score is None:
                any_score_missing = True

        eligible.append(_to_recommendation(creator, score, youtube_channel, instagram_profile))

    eligible.sort(key=lambda r: r.final_score, reverse=True)
    results = eligible[: request.max_results]

    is_mock_data = using_mock_creators or any_score_missing
    return BrandRecommendationResponse(query=request, results=results, is_mock_data=is_mock_data)

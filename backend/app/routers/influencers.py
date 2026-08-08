"""Brand-input -> ranked influencer list endpoint (PROJECT_PLAN.md Section 5,
recommendation engine). Real ranking depends on ML-Core's GAIL/Temporal
outputs feeding the Fusion Layer; until then this returns real creators
from the DB (if any) using their latest stored FusionScore, and falls back
to mock creators + a placeholder fusion score when the DB is empty.
Budget/region/demographic filtering is not yet implemented.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.fusion import compute_fusion_score
from app.models import Creator, FusionScore
from app.schemas import (
    BrandRecommendationRequest,
    BrandRecommendationResponse,
    InfluencerRecommendation,
    ScoreBreakdown,
)

router = APIRouter(tags=["recommendations"])

_MOCK_CREATORS = [
    Creator(unique_id="mock-fitwithpriya", name="FitWithPriya", category="fitness",
            youtube_handle="@FitWithPriya", instagram_handle="@fitwithpriya"),
    Creator(unique_id="mock-gymbro", name="GymBro", category="fitness",
            youtube_handle="@GymBro", instagram_handle="@gymbro"),
    Creator(unique_id="mock-yogaguru", name="YogaGuru", category="lifestyle",
            instagram_handle="@yogaguru", reddit_handle="u/yogaguru"),
]


def _to_recommendation(creator: Creator, score: FusionScore | None) -> InfluencerRecommendation:
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

    return InfluencerRecommendation(
        creator_unique_id=creator.unique_id,
        name=creator.name,
        category=creator.category,
        youtube_handle=creator.youtube_handle,
        instagram_handle=creator.instagram_handle,
        reddit_handle=creator.reddit_handle,
        final_score=final_score,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        estimated_reach=None,
        score_breakdown=breakdown,
    )


@router.post("/recommendations", response_model=BrandRecommendationResponse)
def get_recommendations(
    request: BrandRecommendationRequest, session: Session = Depends(get_session)
) -> BrandRecommendationResponse:
    creators = session.exec(select(Creator).limit(request.max_results)).all()
    is_mock_data = False

    if not creators:
        creators = _MOCK_CREATORS[: request.max_results]
        is_mock_data = True

    results = []
    for creator in creators:
        score = None
        if not is_mock_data:
            score = session.exec(
                select(FusionScore)
                .where(FusionScore.creator_unique_id == creator.unique_id)
                .order_by(FusionScore.computed_at.desc())
            ).first()
            if score is None:
                is_mock_data = True  # real creator, but no real fusion score yet
        results.append(_to_recommendation(creator, score))

    results.sort(key=lambda r: r.final_score, reverse=True)

    return BrandRecommendationResponse(query=request, results=results, is_mock_data=is_mock_data)

"""Brand-input -> ranked influencer list endpoint (PROJECT_PLAN.md Section 5,
recommendation engine).

Spillover is now real via GAIL checkpoint (c6488a6) — see app/spillover.py.
w1 (spillover) real, w2 (sentiment_risk) still 0.5 placeholder (Temporal
0% built, CAPSTONE_NEXT_STEPS.md:822); confidence reflects honest small-N
(N=10) via spillover_half_width (trained ±15pts, inferred/placeholder ±25pts
on 0-100). Track D must read spillover_basis to distinguish.

What changed 2026-08-09 (was previously a no-op stub, see API_CONTRACTS.md):
- budget: hard filter via `estimated_cost` (a placeholder followers/subscribers
  * flat-rate heuristic -- no real rate-card data exists yet). Candidates with
  unknown reach data aren't excluded (can't compute a cost for them).
- target_region / target_demographic / product_category: soft filters. A
  creator is excluded only if we HAVE text signal for them
  (youtube_channels.country/description, instagram_profiles.bio, or --
  for product_category -- creator.category itself) and it does NOT match.
  Creators with no signal data at all are kept -- with Weeks 3-4 scraping
  still ramping up, most creators won't have this data yet, and a hard
  requirement would return empty result sets for almost every query.
  Matching is keyword-overlap (any word >=3 chars in the query appears in
  the combined signal text), not whole-phrase substring -- a whole-phrase
  match almost never hits real bio/description text (added 2026-08-09,
  was whole-phrase-only before, which meant target_demographic in practice
  never excluded anything).
- platform_preference: hard filter -- creator must have a handle on at
  least one of the requested platforms. Unlike the soft filters above,
  "no handle on this platform" is a directly known fact, not missing data.
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
from app.spillover import get_spillover_batch

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


def _extract_keywords(query: str | None) -> list[str]:
    if not query:
        return []
    return [w for w in query.lower().split() if len(w) >= 3]


def _keyword_overlap(keywords: list[str], texts: list[str | None]) -> bool:
    """True if any of `keywords` appears in the combined `texts`.

    Keyword-overlap, not whole-phrase substring: a query like "18-24 fitness
    enthusiasts" almost never appears verbatim in real bio/description text,
    so whole-phrase matching effectively never fires. Deliberately crude
    (no stemming/stopwords) -- a placeholder pending real NLP matching.

    Callers must treat an empty `keywords` list (query too short/unmatchable,
    e.g. "x") as "can't judge" and skip filtering, NOT as a confirmed
    mismatch -- returning False here for that case would otherwise get
    misread as "doesn't match" and wrongly exclude everyone. Found via
    regression testing on 2026-08-09 (test payloads used a 1-char
    product_category, which excluded every real result).
    """
    if not keywords:
        return False
    combined = " ".join(t.lower() for t in texts if t)
    return any(k in combined for k in keywords)


def _has_preferred_platform(creator: Creator, platforms: list[str] | None) -> bool:
    if not platforms:
        return True
    handles = {
        "youtube": creator.youtube_handle,
        "instagram": creator.instagram_handle,
        "reddit": creator.reddit_handles,
    }
    return any(handles.get(p.lower()) for p in platforms)


def _to_recommendation(
    creator: Creator,
    score: FusionScore | None,
    youtube_channel: YouTubeChannel | None,
    instagram_profile: InstagramProfile | None,
    spillover_info: dict | None = None,
) -> InfluencerRecommendation:
    # Resolve spillover: live GAIL if available, else stored or placeholder.
    # spillover_info comes from get_spillover_batch (has spillover_score, basis, confidence_*).
    if spillover_info is not None:
        spillover_score = spillover_info["spillover_score"]
        spillover_basis = spillover_info["basis"]
        spillover_hw = abs(spillover_info["confidence_high"] - spillover_score)
        # Use stored sentiment/creator_feature if we have a row, else 0.5 placeholder (w2 placeholder)
        sentiment = score.sentiment_risk_score if score is not None else 0.5
        creator_feat = score.creator_feature_score if score is not None else 0.5
        final_score, confidence_low, confidence_high, _risk_adj, breakdown = compute_fusion_score(
            spillover_score, sentiment, creator_feat,
            spillover_half_width=spillover_hw, spillover_basis=spillover_basis,
        )
    elif score is not None:
        breakdown = ScoreBreakdown(
            spillover_score=score.spillover_score,
            sentiment_risk_score=score.sentiment_risk_score,
            creator_feature_score=score.creator_feature_score,
            weight_spillover=settings.fusion_weight_spillover,
            weight_sentiment_risk=settings.fusion_weight_sentiment_risk,
            weight_creator_feature=settings.fusion_weight_creator_feature,
        )
        final_score, confidence_low, confidence_high = score.final_score, score.confidence_low, score.confidence_high
        spillover_basis = getattr(score, "spillover_basis", "placeholder")
    else:
        # No stored row and no GAIL info (should not happen — batch always provides), fallback
        final_score, confidence_low, confidence_high, _risk_adj, breakdown = compute_fusion_score(0.5, 0.5, 0.5)
        spillover_basis = "placeholder"

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
        spillover_basis=spillover_basis,  # type: ignore[arg-type]
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
    region_keywords = _extract_keywords(request.target_region)
    demographic_keywords = _extract_keywords(request.target_demographic)
    category_keywords = _extract_keywords(request.product_category)

    # Batch-resolve spillover for all creators once (single GAT forward, cached)
    spillover_map = {}
    if not using_mock_creators:
        try:
            spillover_map = get_spillover_batch([c.creator_id for c in creators])
        except Exception:
            spillover_map = {}

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

        # --- platform_preference filter (hard: no handle = directly known fact) ---
        if not _has_preferred_platform(creator, request.platform_preference):
            continue

        # --- region-proxy filter (soft: only exclude on a confirmed mismatch) ---
        region_signals = [
            youtube_channel.country if youtube_channel else None,
            youtube_channel.description if youtube_channel else None,
            instagram_profile.bio if instagram_profile else None,
        ]
        has_region_signal = any(region_signals)
        if region_keywords and has_region_signal and not _keyword_overlap(region_keywords, region_signals):
            continue

        # --- demographic-proxy filter (soft, same policy) ---
        demographic_signals = [
            instagram_profile.bio if instagram_profile else None,
            youtube_channel.description if youtube_channel else None,
        ]
        has_demographic_signal = any(demographic_signals)
        if demographic_keywords and has_demographic_signal and not _keyword_overlap(
            demographic_keywords, demographic_signals
        ):
            continue

        # --- product_category filter (soft, same policy) ---
        category_signals = [
            creator.category.replace("_", " ") if creator.category else None,
            youtube_channel.description if youtube_channel else None,
            instagram_profile.bio if instagram_profile else None,
        ]
        has_category_signal = any(category_signals)
        if category_keywords and has_category_signal and not _keyword_overlap(
            category_keywords, category_signals
        ):
            continue

        score = None
        if not using_mock_creators:
            score = session.exec(
                select(FusionScore)
                .where(FusionScore.creator_id == creator.creator_id)
                .order_by(FusionScore.computed_at.desc())
            ).first()
            if score is None:
                any_score_missing = True

        spillover_info = spillover_map.get(str(creator.creator_id)) if not using_mock_creators else None
        eligible.append(_to_recommendation(creator, score, youtube_channel, instagram_profile, spillover_info))

    eligible.sort(key=lambda r: r.final_score, reverse=True)
    results = eligible[: request.max_results]

    is_mock_data = using_mock_creators or any_score_missing
    return BrandRecommendationResponse(query=request, results=results, is_mock_data=is_mock_data)

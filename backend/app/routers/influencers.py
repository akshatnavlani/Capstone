"""Brand-input -> ranked influencer list endpoint (PROJECT_PLAN.md Section 5,
recommendation engine).

All three branches are live: spillover from the GAIL checkpoint (as a 0-1
percentile, app/spillover.py), sentiment from the Temporal branch
(app/temporal.py), creator feature from CLIP/BERT (app/creator_features.py).
The confidence interval combines all three (app/fusion.py). Track D must read
spillover_basis to tell trained / inferred / placeholder / isolated apart.

What changed 2026-08-09 (was previously a no-op stub, see API_CONTRACTS.md):
- budget: hard filter via `estimated_cost` (a placeholder followers/subscribers
  * flat-rate heuristic -- no real rate-card data exists yet). Candidates with
  unknown reach data aren't excluded (can't compute a cost for them).
- target_region / target_demographic / product_category: soft filters
  (whole-word, lightly stemmed matching; region also reads country codes,
  the flag, Indian scripts and the creator's name -- see the helpers below).
  A creator is excluded only if we HAVE text signal for them
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

import re
import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.config import settings
from app.creator_features import get_feature_scores
from app.database import get_session
from app.fusion import compute_fusion_score, feature_uncertainty, sentiment_uncertainty
from app.models import Creator, FusionScore, InstagramProfile, YouTubeChannel
from app.schemas import (
    BrandRecommendationRequest,
    BrandRecommendationResponse,
    InfluencerRecommendation,
    ScoreBreakdown,
)
from app.spillover import get_spillover_batch
from app.temporal import get_temporal_batch

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


# Matching rules (PendingWork S7 fixes; the S7 audit measured the old plain-substring test):
#  - a query word matches a whole word of the text after light stemming, so "athletic" finds
#    "athlete" and "shoes" finds "shoe";
#  - a LONG query word (6+ letters) may also match inside a longer word ("cricket" in
#    "cricketer" or "@lancashirecricket");
#  - a SHORT query word must match a whole word: "mat" no longer matches "cinematic" and
#    "night" no longer matches "Knight Riders".
_SUFFIXES = ("ing", "ers", "er", "ies", "es", "ic", "ed", "s", "e")
_SUBSTRING_MIN_LEN = 6


def _stem(word: str) -> str:
    """Strip one common suffix, twice ("athletics" -> "athletic" -> "athlet"), keeping 4+ letters."""
    for _ in range(2):
        for suffix in _SUFFIXES:
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]
                break
        else:
            break
    return word


def _keyword_overlap(keywords: list[str], texts: list[str | None], substring: bool = True) -> bool:
    """True if any of `keywords` matches the combined `texts` (rules above).

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
    stems = {_stem(w) for w in re.findall(r"[a-z0-9]+", combined)}
    for raw in keywords:
        k = re.sub(r"[^\w]", "", raw)
        if not k:
            continue
        if substring and len(k) >= _SUBSTRING_MIN_LEN and k in combined:
            return True
        if k in stems or _stem(k) in stems:
            return True
    return False


# Region matching. The old test needed the English word "india" in a bio or description, so it dropped
# creators whose YouTube country is the code "IN", who wrote the flag or a +91 number, who write in an
# Indian script, or who have "India" in their own name (S7: ~80% of 116 region drops were Indian creators).
_COUNTRY_CODE_NAMES = {
    "in": "india", "us": "united states usa america", "gb": "united kingdom uk britain england", "au": "australia",
    "ae": "united arab emirates uae dubai", "ca": "canada", "nz": "new zealand", "za": "south africa",
    "pk": "pakistan", "bd": "bangladesh", "lk": "sri lanka", "np": "nepal",
}
_REGION_ALIASES = {"india": ("indian", "bharat", "hindustan")}
_REGION_MARKERS = {"india": ("\U0001f1ee\U0001f1f3", "+91")}  # flag emoji, phone prefix
_INDIC_SCRIPT = re.compile("[\u0900-\u0DFF]")  # Devanagari, Bengali, Gurmukhi, Gujarati, Tamil, Telugu, Kannada, Malayalam


def _region_overlap(keywords: list[str], texts: list[str | None], name: str | None = None) -> bool:
    """Like `_keyword_overlap`, plus: a bare ISO country code ("IN") counts as the country's name, the
    creator's own name counts as text, and for India the flag, a +91 number and Indian scripts count.
    The name is evidence for a match only: it never makes a creator "have region text", so creators
    with no region text at all are still kept by the caller."""
    texts = list(texts) + [name]
    codes = [_COUNTRY_CODE_NAMES.get(t.strip().lower()) for t in texts if t and len(t.strip()) == 2]
    all_texts = texts + [c for c in codes if c]
    if _keyword_overlap(keywords, all_texts):
        return True
    # aliases ("indian") match whole words only: as a substring "indian" would match "Indiana"
    if _keyword_overlap([a for k in keywords for a in _REGION_ALIASES.get(k, ())], all_texts, substring=False):
        return True
    raw = " ".join(t for t in all_texts if t)
    for k in keywords:
        if any(m in raw for m in _REGION_MARKERS.get(k, ())):
            return True
        if k == "india" and _INDIC_SCRIPT.search(raw):
            return True
    return False


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
    temporal_info: dict | None = None,
    feature_info: dict | None = None,
) -> InfluencerRecommendation:
    # Resolve spillover: live GAIL if available, else stored or placeholder.
    # spillover_info comes from get_spillover_batch (has spillover_score, basis, confidence_*).
    if spillover_info is not None:
        # Fusion works on the 0-1 percentile of the GAIL lift, not the raw lift.
        spillover_score = spillover_info["spillover_unit"]
        spillover_basis = spillover_info["basis"]
        spillover_hw = (spillover_info["unit_high"] - spillover_info["unit_low"]) / 2
        # Real Temporal-branch score when this creator has scored comments
        # (app/temporal.py); otherwise stored sentiment if we have a row, else 0.5.
        if temporal_info is not None and temporal_info["basis"] == "scored":
            sentiment = temporal_info["sentiment_risk_score"]
            sentiment_hw = sentiment_uncertainty(temporal_info["n_comments"])
        else:
            sentiment = score.sentiment_risk_score if score is not None else 0.5
            sentiment_hw = sentiment_uncertainty(None)
        # Real CLIP/BERT relevance + metadata score (app/creator_features.py) once
        # the models are loaded; otherwise stored score if we have a row, else 0.5.
        if feature_info is not None:
            creator_feat = feature_info["score"]
        else:
            creator_feat = score.creator_feature_score if score is not None else 0.5
        final_score, confidence_low, confidence_high, _risk_adj, breakdown = compute_fusion_score(
            spillover_score, sentiment, creator_feat,
            spillover_half_width=spillover_hw, spillover_basis=spillover_basis,
            sentiment_half_width=sentiment_hw,
            feature_half_width=feature_uncertainty(feature_info["basis"] if feature_info else None),
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

    # Temporal branch: real sentiment where comments were scored (one cached pass).
    temporal_map = get_temporal_batch(session) if not using_mock_creators else {}
    # Creator feature score for this brief; None until the models have loaded.
    feature_map = get_feature_scores(request.product_category) if not using_mock_creators else None

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
        if region_keywords and has_region_signal and not _region_overlap(region_keywords, region_signals, creator.name):
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

        spillover_info = spillover_map.get(str(creator.creator_id)) if not using_mock_creators else None
        temporal_info = temporal_map.get(str(creator.creator_id)) if not using_mock_creators else None
        feature_info = feature_map.get(str(creator.creator_id)) if feature_map else None
        eligible.append(
            _to_recommendation(creator, score, youtube_channel, instagram_profile, spillover_info, temporal_info, feature_info)
        )

    eligible.sort(key=lambda r: r.final_score, reverse=True)
    results = eligible[: request.max_results]

    # Scores are computed live from the three branches, so a missing stored row no
    # longer makes the response mock: only the demo creators do.
    return BrandRecommendationResponse(query=request, results=results, is_mock_data=using_mock_creators)

"""Pydantic request/response schemas (API I/O), kept separate from the DB
table models in models.py so the wire contract can evolve independently of
storage. See API_CONTRACTS.md at repo root for the full documented contract.

`creator_id` (uuid) is the cross-track join key, matching Track A's real
`creators.creator_id` column (see SCHEMA.md on track-a-data-infra). This
replaced the earlier placeholder `creator_unique_id: str` field on
2026-08-09 once Track A's actual schema was published — a breaking change,
flagged in API_CONTRACTS.md.
"""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---- Shared ----------------------------------------------------------------

class ScoreBreakdown(BaseModel):
    spillover_score: float = Field(description="GAIL branch output, 0-1")
    sentiment_risk_score: float = Field(description="Temporal branch sentiment/risk output, 0-1")
    creator_feature_score: float = Field(description="Creator feature score (CLIP+BERT+metadata), 0-1")
    weight_spillover: float
    weight_sentiment_risk: float
    weight_creator_feature: float


# ---- Brand-input / recommendation endpoint ---------------------------------

class BrandRecommendationRequest(BaseModel):
    product_category: str = Field(examples=["fitness apparel"])
    budget: float = Field(gt=0, allow_inf_nan=False, description="Budget in INR")
    target_region: Optional[str] = Field(default=None, description="Region proxy, e.g. 'IN-south', 'US'")
    target_demographic: Optional[str] = Field(default=None, description="Demographic proxy, e.g. '18-24 fitness enthusiasts'")
    platform_preference: Optional[list[str]] = Field(default=None, description="Subset of ['youtube','instagram','reddit']")
    max_results: int = Field(default=10, ge=1, le=50)


class InfluencerRecommendation(BaseModel):
    creator_id: uuid.UUID
    name: str
    category: Optional[str] = None
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handles: list[str] = Field(default_factory=list)
    final_score: float = Field(description="0-100")
    confidence_low: float
    confidence_high: float
    estimated_reach: Optional[int] = Field(default=None, description="Engagement-per-rupee proxy, not sales/conversion")
    estimated_cost: Optional[float] = Field(default=None, description="Placeholder cost heuristic used for budget filtering, see API_CONTRACTS.md")
    score_breakdown: ScoreBreakdown


class BrandRecommendationResponse(BaseModel):
    query: BrandRecommendationRequest
    results: list[InfluencerRecommendation]
    is_mock_data: bool = Field(description="True until real Fusion Layer + DB data is wired in")


# ---- Ingestion endpoints -----------------------------------------------------
# NOTE (2026-08-09): Track A's real ingestion orchestrator (scripts/ingestion/
# orchestrator.py on track-a-data-infra) writes directly to the shared Supabase
# DB via DATABASE_URL, bypassing these endpoints entirely. These remain as a
# secondary/manual write path (testing, other tracks seeding data) rather than
# the primary ingestion pipeline -- see API_CONTRACTS.md.
#
# is_sponsored / sponsorship_raw_matches are optional and nullable on all
# content-level ingest schemas below: Track A does NOT pre-compute this, and
# neither does Track C yet (that's the Weeks 7-8 labeling pipeline). Ingest
# callers should omit it (or pass null) until then.

class CreatorIngest(BaseModel):
    creator_id: Optional[uuid.UUID] = None  # generated if omitted
    name: str
    category: Optional[Literal["athlete", "team", "league", "fitness_influencer", "lifestyle_influencer", "other"]] = None
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handles: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CreatorRelatedAccountIngest(BaseModel):
    creator_id: uuid.UUID
    platform: Literal["youtube", "instagram", "reddit"]
    handle: str
    relation_type: Optional[Literal["team", "league", "frequent_collaborator", "fan_page", "family"]] = None


class YouTubeChannelIngest(BaseModel):
    channel_id: str
    creator_id: Optional[uuid.UUID] = None
    channel_handle: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    subscriber_count: Optional[int] = None
    view_count: Optional[int] = None
    video_count: Optional[int] = None
    channel_created_at: Optional[datetime] = None
    country: Optional[str] = None


class YouTubeVideoIngest(BaseModel):
    video_id: str
    channel_id: str
    creator_id: Optional[uuid.UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    published_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    is_sponsored: Optional[bool] = None
    sponsorship_raw_matches: Optional[list[str]] = None


class InstagramProfileIngest(BaseModel):
    username: str
    creator_id: Optional[uuid.UUID] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    is_verified: Optional[bool] = None


class InstagramPostIngest(BaseModel):
    post_id: str
    username: str
    creator_id: Optional[uuid.UUID] = None
    caption: Optional[str] = None
    posted_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    media_type: Optional[str] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    hashtags: list[str] = Field(default_factory=list)
    is_sponsored: Optional[bool] = None
    sponsorship_raw_matches: Optional[list[str]] = None


class RedditProfileIngest(BaseModel):
    username: str
    creator_id: Optional[uuid.UUID] = None
    account_created_at: Optional[datetime] = None
    comment_karma: Optional[int] = None
    link_karma: Optional[int] = None


class RedditPostIngest(BaseModel):
    post_id: str
    subreddit: str
    creator_id: Optional[uuid.UUID] = None
    author_username: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    posted_at: Optional[datetime] = None
    score: Optional[int] = None
    num_comments: Optional[int] = None
    is_sponsored: Optional[bool] = None
    sponsorship_raw_matches: Optional[list[str]] = None


class IngestionResponse(BaseModel):
    received: int
    created: int
    updated: int


# ---- Fusion Layer score endpoint -------------------------------------------

class FusionScoreComputeRequest(BaseModel):
    creator_id: uuid.UUID
    spillover_score: float = Field(ge=0, le=1, allow_inf_nan=False, description="From GAIL branch")
    sentiment_risk_score: float = Field(ge=0, le=1, allow_inf_nan=False, description="From Temporal branch (incl. sentiment propagation)")
    creator_feature_score: float = Field(ge=0, le=1, allow_inf_nan=False, description="From creator feature extraction")


class FusionScoreResponse(BaseModel):
    creator_id: uuid.UUID
    final_score: float = Field(description="0-100")
    confidence_low: float
    confidence_high: float
    risk_adjustment: float
    breakdown: ScoreBreakdown
    computed_at: datetime
    is_placeholder_formula: bool = Field(
        description="True until weights are calibrated against held-out historical outcomes (Section 4)"
    )


# ---- Monitoring / alerts endpoint ------------------------------------------

class AlertCreate(BaseModel):
    creator_id: uuid.UUID
    severity: Literal["low", "medium", "high"]
    reason: str
    source: str = Field(default="sentiment_propagation")
    propagated_from_creator_id: Optional[uuid.UUID] = Field(
        default=None,
        description=(
            "If this alert exists because risk propagated from another creator's "
            "controversy (Section 3b Sentiment Propagation / Section 5 Monitoring), "
            "that creator's id. Null for alerts sourced directly from this creator. "
            "Added 2026-08-09 ahead of the Weeks 14-15 Sentiment Propagation work "
            "landing, so Track D doesn't need a second breaking change later -- "
            "expect this to stay null until then."
        ),
    )


class AlertResponse(BaseModel):
    id: int
    creator_id: uuid.UUID
    severity: str
    reason: str
    source: str
    propagated_from_creator_id: Optional[uuid.UUID] = None
    created_at: datetime
    resolved: bool


# ---- Labeling pipeline (is_sponsored, PROJECT_PLAN.md Section 2) -----------

class LabelingPlatformResult(BaseModel):
    checked: int = Field(description="Rows with is_sponsored IS NULL that were processed")
    labeled_sponsored: int = Field(description="Of those, how many were labeled True")


class LabelingRunResponse(BaseModel):
    youtube_videos: LabelingPlatformResult
    instagram_posts: LabelingPlatformResult
    reddit_posts: LabelingPlatformResult


# ---- Feature store (DB -> Track B's ml/schema.py input shape) --------------
# See backend/app/feature_store.py for the transformation logic and the
# known-gaps writeup (reputation_score, co_occurs_with).

class CreatorFeatureRecord(BaseModel):
    creator_id: uuid.UUID
    name: str
    category: Optional[str] = None
    category_one_hot: list[int] = Field(description="Order matches Track B's ml/schema.py CREATOR_CATEGORIES exactly")
    log_subscriber_count: Optional[float] = None
    engagement_rate: Optional[float] = None
    reputation_score: Optional[float] = Field(
        default=None,
        description="Always null currently -- no Track A table has a reputation_score source column. Open cross-track item, see API_CONTRACTS.md.",
    )
    raw_text: str = Field(description="Scrubbed (URLs/HTML/mentions removed, Section 2) and staged for Track B's Weeks 9-10 BERT embedding step -- not embedded here")
    thumbnail_urls: list[str] = Field(description="Staged for Track B's Weeks 9-10 CLIP embedding step -- not embedded here")
    is_stub: bool = Field(description="True if there's no text/thumbnail data yet to embed")


class CollaborationEdge(BaseModel):
    source_creator_id: uuid.UUID
    target_creator_id: uuid.UUID
    weight: float = Field(description="Count of matched frequent_collaborator relations between this pair")


class SponsorshipEdge(BaseModel):
    creator_id: uuid.UUID
    brand_id: uuid.UUID
    content_id: str
    platform: Literal["youtube", "instagram", "reddit"]


# ---- Health -----------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str

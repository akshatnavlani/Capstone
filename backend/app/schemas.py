"""Pydantic request/response schemas (API I/O), kept separate from the DB
table models in models.py so the wire contract can evolve independently of
storage. See API_CONTRACTS.md at repo root for the full documented contract.
"""

from datetime import datetime
from typing import Optional

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
    budget: float = Field(gt=0, description="Budget in INR")
    target_region: Optional[str] = Field(default=None, description="Region proxy, e.g. 'IN-south', 'US'")
    target_demographic: Optional[str] = Field(default=None, description="Demographic proxy, e.g. '18-24 fitness enthusiasts'")
    platform_preference: Optional[list[str]] = Field(default=None, description="Subset of ['youtube','instagram','reddit']")
    max_results: int = Field(default=10, ge=1, le=50)


class InfluencerRecommendation(BaseModel):
    creator_unique_id: str
    name: str
    category: Optional[str] = None
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handle: Optional[str] = None
    final_score: float = Field(description="0-100")
    confidence_low: float
    confidence_high: float
    estimated_reach: Optional[int] = Field(default=None, description="Engagement-per-rupee proxy, not sales/conversion")
    score_breakdown: ScoreBreakdown


class BrandRecommendationResponse(BaseModel):
    query: BrandRecommendationRequest
    results: list[InfluencerRecommendation]
    is_mock_data: bool = Field(description="True until real Fusion Layer + DB data is wired in")


# ---- Ingestion endpoints (Track A -> this API) -----------------------------

class CreatorIngest(BaseModel):
    unique_id: str
    name: str
    category: Optional[str] = None
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handle: Optional[str] = None
    related_accounts: Optional[list[str]] = None
    prior_endorsements: Optional[list[str]] = None
    bio_text: Optional[str] = None
    posting_timezone: Optional[str] = None
    reputation_score: Optional[float] = None
    is_bot_suspected: bool = False


class YouTubePostIngest(BaseModel):
    creator_unique_id: str
    platform_post_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    is_sponsored: bool = False


class InstagramPostIngest(BaseModel):
    creator_unique_id: str
    platform_post_id: str
    caption: Optional[str] = None
    media_type: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    is_sponsored: bool = False


class RedditPostIngest(BaseModel):
    creator_unique_id: str
    platform_post_id: str
    subreddit: Optional[str] = None
    body: Optional[str] = None
    published_at: Optional[datetime] = None
    score: Optional[int] = None
    num_comments: Optional[int] = None
    is_sponsored: bool = False


class IngestionResponse(BaseModel):
    received: int
    created: int
    updated: int


# ---- Fusion Layer score endpoint -------------------------------------------

class FusionScoreComputeRequest(BaseModel):
    creator_unique_id: str
    spillover_score: float = Field(ge=0, le=1, description="From GAIL branch")
    sentiment_risk_score: float = Field(ge=0, le=1, description="From Temporal branch (incl. sentiment propagation)")
    creator_feature_score: float = Field(ge=0, le=1, description="From creator feature extraction")


class FusionScoreResponse(BaseModel):
    creator_unique_id: str
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
    creator_unique_id: str
    severity: str = Field(description="low | medium | high")
    reason: str
    source: str = Field(default="sentiment_propagation")


class AlertResponse(BaseModel):
    id: int
    creator_unique_id: str
    severity: str
    reason: str
    source: str
    created_at: datetime
    resolved: bool


# ---- Health -----------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str

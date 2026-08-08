"""DB table models.

PROVISIONAL: mirrors the seed-table + per-platform-table design from
PROJECT_PLAN.md Section 1 / Capstone Documents.md ("How do we store this
data"). Track A owns the source-of-truth schema (see SCHEMA.md on
track-a-data-infra once published) -- adjust these to match once that
lands. `unique_id` is the cross-track join key.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Creator(SQLModel, table=True):
    """Seed table: one row per influencer/creator entity."""

    id: Optional[int] = Field(default=None, primary_key=True)
    unique_id: str = Field(unique=True, index=True)
    name: str
    category: Optional[str] = None  # athlete, team, league, fitness, lifestyle, brand
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handle: Optional[str] = None
    related_accounts: Optional[str] = None  # JSON-encoded list of related handles
    prior_endorsements: Optional[str] = None  # JSON-encoded list

    # Region/demographic proxy signals (Section 1: no free third-party audience analytics)
    bio_text: Optional[str] = None
    posting_timezone: Optional[str] = None

    reputation_score: Optional[float] = None
    is_bot_suspected: bool = False

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class YouTubePost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    creator_unique_id: str = Field(foreign_key="creator.unique_id", index=True)
    platform_post_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    is_sponsored: bool = False
    scraped_at: datetime = Field(default_factory=utcnow)


class InstagramPost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    creator_unique_id: str = Field(foreign_key="creator.unique_id", index=True)
    platform_post_id: str
    caption: Optional[str] = None
    media_type: Optional[str] = None  # image, video, reel, carousel
    thumbnail_url: Optional[str] = None
    published_at: Optional[datetime] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    is_sponsored: bool = False
    scraped_at: datetime = Field(default_factory=utcnow)


class RedditPost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    creator_unique_id: str = Field(foreign_key="creator.unique_id", index=True)
    platform_post_id: str
    subreddit: Optional[str] = None
    body: Optional[str] = None
    published_at: Optional[datetime] = None
    score: Optional[int] = None  # upvotes - downvotes
    num_comments: Optional[int] = None
    is_sponsored: bool = False
    scraped_at: datetime = Field(default_factory=utcnow)


class FusionScore(SQLModel, table=True):
    """Persisted output of the Fusion Layer (Section 4) for a creator."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creator_unique_id: str = Field(foreign_key="creator.unique_id", index=True)
    spillover_score: float
    sentiment_risk_score: float
    creator_feature_score: float
    final_score: float
    confidence_low: float
    confidence_high: float
    risk_adjustment: float
    computed_at: datetime = Field(default_factory=utcnow)


class RiskAlert(SQLModel, table=True):
    """Monitoring/alerts feed (Section 5), fed by Track B's sentiment
    propagation output once available."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creator_unique_id: str = Field(foreign_key="creator.unique_id", index=True)
    severity: str  # low, medium, high
    reason: str
    source: str  # e.g. "sentiment_propagation", "manual"
    created_at: datetime = Field(default_factory=utcnow)
    resolved: bool = False

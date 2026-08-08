"""DB table models.

Two ownership zones, per API_CONTRACTS.md:

1. Track A's live schema (`Brand`, `Creator`, `YouTubeChannel`,
   `YouTubeVideo`, `InstagramProfile`, `InstagramPost`, `RedditProfile`,
   `RedditPost`) — mirrors `SCHEMA.md` +
   `supabase/migrations/20260808163402_init_schema.sql` +
   `20260809010000_add_brands.sql` on `origin/track-a-data-infra` as of
   2026-08-09. Track A owns migrations for these tables; Track C only
   reads/writes them via this ORM mapping. Re-diff against their SCHEMA.md
   if it changes — don't assume this stays in sync automatically.

   `is_sponsored` / `sponsorship_raw_matches` are nullable by design: Track A
   stores raw scraped text only. Track C owns the disclosure-tag labeling
   pipeline that populates them (PROJECT_PLAN.md Section 6, Weeks 7-8) — do
   not assume these arrive pre-computed from ingestion callers.

   Track A's `reddit_handles` (creators), `tags` (youtube_videos), and
   `hashtags` (instagram_posts) are real Postgres `text[]` columns
   (`sqlalchemy.dialects.postgresql.ARRAY`). These use
   `.with_variant(JSON(), "sqlite")` (see `_string_array_column()` below) so
   the same model works against both: a native array on real Postgres, a
   JSON list on the SQLite local-dev fallback. Without this, these tables
   wouldn't exist at all locally and every query against them would raise
   instead of falling through to `/recommendations`'s mock-fallback path --
   found via adversarial self-check on 2026-08-09.

2. Track C's own tables (`FusionScore`, `RiskAlert`) — Track C owns
   migrations for these; `init_db()` creates them (idempotent) against
   whichever DATABASE_URL is configured, SQLite or Postgres alike.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _string_array_column():
    """Real Postgres text[] in production; JSON list on the SQLite dev fallback.

    Must be ARRAY(String), not ARRAY(str) -- the bare Python type coerces
    fine for DDL/table creation but breaks reading rows back from real
    Postgres (`AttributeError: 'str' object has no attribute 'dialect_impl'`
    in the array result processor). Only surfaces when actually querying
    real data, not against the SQLite/JSON fallback path -- caught testing
    against the real Supabase instance on 2026-08-09.
    """
    return Column(ARRAY(String).with_variant(JSON(), "sqlite"))


# ---- Track A-owned tables (read/write mapping only, no migration ownership) --

class Brand(SQLModel, table=True):
    """Added by Track A 2026-08-09 (migration 20260809010000_add_brands.sql),
    bounded scope: populated only from brand names extracted out of
    sponsorship-disclosure text already on creator content rows, not an
    open-ended brand-discovery crawl. Gives Track B's GAIL graph a real
    (brand, sponsors, creator) edge endpoint."""

    __tablename__ = "brands"

    brand_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    category: Optional[str] = None
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handle: Optional[str] = None
    follower_count: Optional[int] = None
    post_count: Optional[int] = None
    is_verified: Optional[bool] = None
    source: str = "sponsorship_mention"
    fetched_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Creator(SQLModel, table=True):
    __tablename__ = "creators"

    creator_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    category: Optional[str] = None  # athlete | team | league | fitness_influencer | lifestyle_influencer | other
    youtube_handle: Optional[str] = None
    instagram_handle: Optional[str] = None
    reddit_handles: list[str] = Field(default_factory=list, sa_column=_string_array_column())
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class YouTubeChannel(SQLModel, table=True):
    __tablename__ = "youtube_channels"

    channel_id: str = Field(primary_key=True)
    creator_id: Optional[uuid.UUID] = Field(default=None, foreign_key="creators.creator_id", index=True)
    channel_handle: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    subscriber_count: Optional[int] = None
    view_count: Optional[int] = None
    video_count: Optional[int] = None
    channel_created_at: Optional[datetime] = None
    country: Optional[str] = None
    is_bot_flagged: Optional[bool] = None
    bot_score: Optional[float] = None
    fetched_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class YouTubeVideo(SQLModel, table=True):
    __tablename__ = "youtube_videos"

    video_id: str = Field(primary_key=True)
    channel_id: str = Field(foreign_key="youtube_channels.channel_id", index=True)
    creator_id: Optional[uuid.UUID] = Field(default=None, foreign_key="creators.creator_id", index=True)
    title: Optional[str] = None
    description: Optional[str] = None
    published_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    tags: list[str] = Field(default_factory=list, sa_column=_string_array_column())
    is_sponsored: Optional[bool] = None  # null = not yet labeled (Track C, Weeks 7-8)
    sponsorship_raw_matches: Optional[list] = Field(default=None, sa_column=Column(JSON))
    brand_id: Optional[uuid.UUID] = Field(default=None, foreign_key="brands.brand_id", index=True)
    fetched_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class InstagramProfile(SQLModel, table=True):
    __tablename__ = "instagram_profiles"

    username: str = Field(primary_key=True)
    creator_id: Optional[uuid.UUID] = Field(default=None, foreign_key="creators.creator_id", index=True)
    full_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    is_verified: Optional[bool] = None
    is_bot_flagged: Optional[bool] = None
    bot_score: Optional[float] = None
    fetched_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class InstagramPost(SQLModel, table=True):
    __tablename__ = "instagram_posts"

    post_id: str = Field(primary_key=True)
    username: str = Field(foreign_key="instagram_profiles.username", index=True)
    creator_id: Optional[uuid.UUID] = Field(default=None, foreign_key="creators.creator_id", index=True)
    caption: Optional[str] = None
    posted_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    media_type: Optional[str] = None  # photo | video | carousel | reel
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    hashtags: list[str] = Field(default_factory=list, sa_column=_string_array_column())
    is_sponsored: Optional[bool] = None
    sponsorship_raw_matches: Optional[list] = Field(default=None, sa_column=Column(JSON))
    brand_id: Optional[uuid.UUID] = Field(default=None, foreign_key="brands.brand_id", index=True)
    fetched_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class RedditProfile(SQLModel, table=True):
    __tablename__ = "reddit_profiles"

    username: str = Field(primary_key=True)
    creator_id: Optional[uuid.UUID] = Field(default=None, foreign_key="creators.creator_id", index=True)
    account_created_at: Optional[datetime] = None
    comment_karma: Optional[int] = None
    link_karma: Optional[int] = None
    is_bot_flagged: Optional[bool] = None
    bot_score: Optional[float] = None
    fetched_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class RedditPost(SQLModel, table=True):
    __tablename__ = "reddit_posts"

    post_id: str = Field(primary_key=True)
    subreddit: str
    creator_id: Optional[uuid.UUID] = Field(default=None, foreign_key="creators.creator_id", index=True)
    author_username: Optional[str] = Field(default=None, foreign_key="reddit_profiles.username")
    title: Optional[str] = None
    body: Optional[str] = None
    posted_at: Optional[datetime] = None
    score: Optional[int] = None
    num_comments: Optional[int] = None
    is_sponsored: Optional[bool] = None
    sponsorship_raw_matches: Optional[list] = Field(default=None, sa_column=Column(JSON))
    brand_id: Optional[uuid.UUID] = Field(default=None, foreign_key="brands.brand_id", index=True)
    fetched_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


# ---- Track C-owned tables (migration ownership: init_db() creates these) ----

class FusionScore(SQLModel, table=True):
    """Persisted output of the Fusion Layer (Section 4) for a creator."""

    id: Optional[int] = Field(default=None, primary_key=True)
    creator_id: uuid.UUID = Field(index=True)
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
    creator_id: uuid.UUID = Field(index=True)
    severity: str  # low, medium, high
    reason: str
    source: str  # e.g. "sentiment_propagation", "manual"
    created_at: datetime = Field(default_factory=utcnow)
    resolved: bool = False


# Tables Track C owns migrations for (used by database.init_db() so we never
# touch Track A's tables, which already exist and are migrated by them).
TRACK_C_OWNED_TABLES = [FusionScore.__table__, RiskAlert.__table__]

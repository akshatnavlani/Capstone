"""DB -> feature-store pipeline (PROJECT_PLAN.md Section 6, Weeks 5-6).

Transforms Track A's raw ingested tables into the shape Track B's GAIL
branch (`ml/schema.py` on track-b-ml-core) and Track C's own scoring logic
need to consume. Deliberately does NOT compute CLIP/BERT embeddings itself
-- that's Track B's Weeks 9-10 deliverable (confirmed via
GRAPH_SCHEMA.md's "What Track A needs to produce" section and
PROJECT_PLAN.md Section 6 row 9-10, which assigns "Run CLIP + BERT feature
extraction across dataset" to Track B, not Track C). This module stages the
raw inputs those embeddings need (text, thumbnail URLs) plus the numeric/
categorical metadata segment of Track B's creator feature vector
(`ml/schema.py` CREATOR_METADATA_DIM = log_subscriber_count + engagement_rate
+ reputation_score + category one-hot) that doesn't require a trained model
to compute.

Known gaps, flagged rather than fabricated:
- `reputation_score`: Track B's ml/schema.py expects this in the metadata
  segment, but no Track A table has a reputation_score source column
  anywhere (checked SCHEMA.md 2026-08-09). Always None here until a real
  source is defined -- open cross-track item, see API_CONTRACTS.md.
- `co_occurs_with` edges (platform co-occurrence, PROJECT_PLAN.md Section
  3a): Track A's schema has no signal for "these creators appeared
  together in the same content" (no co-starring/tagging table). Not built
  here -- would require either a new Track A ingestion field or inferring
  it from something not yet collected. Flagged, not fabricated.
- `sponsors`/`sponsored_by` edges will be empty until `is_sponsored` is
  populated (Track C's own Weeks 7-8 deliverable) -- expected, not a bug.
"""

import math
import uuid
from collections import defaultdict

from sqlmodel import Session, select

from app.models import (
    Creator,
    CreatorRelatedAccount,
    InstagramPost,
    InstagramProfile,
    RedditPost,
    YouTubeChannel,
    YouTubeVideo,
)
from app.schemas import CollaborationEdge, CreatorFeatureRecord, SponsorshipEdge

# Must match Track B's ml/schema.py CREATOR_CATEGORIES exactly (confirmed via
# git show origin/track-b-ml-core:ml/schema.py, 2026-08-09) -- order matters,
# it defines the one-hot index Track B's model reads.
CREATOR_CATEGORIES = (
    "athlete",
    "team",
    "league",
    "fitness_influencer",
    "lifestyle_influencer",
    "other",
)

# Caps text/thumbnail aggregation per creator -- defensive once real content
# volume lands (Weeks 3-4 scraping), not needed against today's empty tables.
_MAX_CONTENT_ITEMS = 20


def _normalize_handle(handle: str) -> str:
    h = handle.strip().lower()
    for prefix in ("@", "u/", "r/"):
        if h.startswith(prefix):
            h = h[len(prefix):]
    return h


def _category_one_hot(category: str | None) -> list[int]:
    vec = [0] * len(CREATOR_CATEGORIES)
    if category in CREATOR_CATEGORIES:
        vec[CREATOR_CATEGORIES.index(category)] = 1
    return vec


def _compute_engagement_rate(
    youtube_videos: list[YouTubeVideo],
    instagram_profile: InstagramProfile | None,
    instagram_posts: list[InstagramPost],
) -> float | None:
    """(likes + comments) / reach, pooled across all known content.

    Reddit posts excluded -- no per-post reach denominator exists without a
    real audience-size concept for Reddit (subreddit membership isn't the
    same thing as a personal follower count), so including them would mean
    fabricating a denominator rather than deriving one.
    """
    total_engagement = 0
    total_reach = 0
    for v in youtube_videos:
        if v.view_count:
            total_engagement += (v.like_count or 0) + (v.comment_count or 0)
            total_reach += v.view_count
    if instagram_profile and instagram_profile.follower_count:
        for p in instagram_posts:
            total_engagement += (p.like_count or 0) + (p.comment_count or 0)
            total_reach += instagram_profile.follower_count

    return total_engagement / total_reach if total_reach else None


def build_creator_features(session: Session) -> list[CreatorFeatureRecord]:
    creators = session.exec(select(Creator)).all()
    if not creators:
        return []

    creator_ids = [c.creator_id for c in creators]
    youtube_channels = {
        yc.creator_id: yc
        for yc in session.exec(select(YouTubeChannel).where(YouTubeChannel.creator_id.in_(creator_ids))).all()
    }
    instagram_profiles = {
        ip.creator_id: ip
        for ip in session.exec(select(InstagramProfile).where(InstagramProfile.creator_id.in_(creator_ids))).all()
    }

    videos_by_creator = defaultdict(list)
    for v in session.exec(select(YouTubeVideo).where(YouTubeVideo.creator_id.in_(creator_ids))).all():
        videos_by_creator[v.creator_id].append(v)

    posts_by_creator = defaultdict(list)
    for p in session.exec(select(InstagramPost).where(InstagramPost.creator_id.in_(creator_ids))).all():
        posts_by_creator[p.creator_id].append(p)

    records = []
    for creator in creators:
        yc = youtube_channels.get(creator.creator_id)
        ip = instagram_profiles.get(creator.creator_id)
        videos = videos_by_creator.get(creator.creator_id, [])
        posts = posts_by_creator.get(creator.creator_id, [])

        reach = max((yc.subscriber_count if yc else 0) or 0, (ip.follower_count if ip else 0) or 0)
        log_subscriber_count = math.log1p(reach) if reach else None

        raw_text_parts = []
        if yc and yc.description:
            raw_text_parts.append(yc.description)
        if ip and ip.bio:
            raw_text_parts.append(ip.bio)
        for v in videos[:_MAX_CONTENT_ITEMS]:
            raw_text_parts += [t for t in (v.title, v.description) if t]
        for p in posts[:_MAX_CONTENT_ITEMS]:
            if p.caption:
                raw_text_parts.append(p.caption)
        raw_text = " ".join(raw_text_parts)

        thumbnail_urls = [v.thumbnail_url for v in videos[:_MAX_CONTENT_ITEMS] if v.thumbnail_url]
        thumbnail_urls += [p.thumbnail_url for p in posts[:_MAX_CONTENT_ITEMS] if p.thumbnail_url]

        records.append(CreatorFeatureRecord(
            creator_id=creator.creator_id,
            name=creator.name,
            category=creator.category,
            category_one_hot=_category_one_hot(creator.category),
            log_subscriber_count=log_subscriber_count,
            engagement_rate=_compute_engagement_rate(videos, ip, posts),
            reputation_score=None,
            raw_text=raw_text,
            thumbnail_urls=thumbnail_urls,
            is_stub=not raw_text and not thumbnail_urls,
        ))

    return records


def build_collaboration_edges(session: Session) -> list[CollaborationEdge]:
    """`(creator, collaborates_with, creator)`, both directions, per Track
    B's ml/schema.py (they don't apply ToUndirected() at load time).

    Resolved from creator_related_accounts.handle -- a free-text platform
    handle, not a FK -- matched (case-insensitive, @/u//r/ stripped)
    against every other creator's own handles. Rows that don't resolve to a
    known creator (most won't, until far more creators are seeded) are
    silently skipped, not an error.
    """
    creators = session.exec(select(Creator)).all()
    if not creators:
        return []

    handle_maps: dict[str, dict[str, uuid.UUID]] = {"youtube": {}, "instagram": {}, "reddit": {}}
    for c in creators:
        if c.youtube_handle:
            handle_maps["youtube"][_normalize_handle(c.youtube_handle)] = c.creator_id
        if c.instagram_handle:
            handle_maps["instagram"][_normalize_handle(c.instagram_handle)] = c.creator_id
        for h in c.reddit_handles:
            handle_maps["reddit"][_normalize_handle(h)] = c.creator_id

    pair_weights: dict[tuple[str, str], int] = defaultdict(int)
    related = session.exec(
        select(CreatorRelatedAccount).where(CreatorRelatedAccount.relation_type == "frequent_collaborator")
    ).all()
    for row in related:
        target_id = handle_maps.get(row.platform, {}).get(_normalize_handle(row.handle))
        if target_id and target_id != row.creator_id:
            pair = tuple(sorted((str(row.creator_id), str(target_id))))
            pair_weights[pair] += 1

    edges = []
    for (a, b), weight in pair_weights.items():
        edges.append(CollaborationEdge(source_creator_id=uuid.UUID(a), target_creator_id=uuid.UUID(b), weight=float(weight)))
        edges.append(CollaborationEdge(source_creator_id=uuid.UUID(b), target_creator_id=uuid.UUID(a), weight=float(weight)))
    return edges


def build_sponsorship_edges(session: Session) -> list[SponsorshipEdge]:
    """`(brand, sponsors, creator)`. Empty until is_sponsored is populated
    (Track C's own Weeks 7-8 labeling pipeline) -- expected, not a bug."""
    edges = []
    for v in session.exec(
        select(YouTubeVideo).where(
            YouTubeVideo.is_sponsored == True,  # noqa: E712
            YouTubeVideo.brand_id.is_not(None),
            YouTubeVideo.creator_id.is_not(None),
        )
    ).all():
        edges.append(SponsorshipEdge(creator_id=v.creator_id, brand_id=v.brand_id, content_id=v.video_id, platform="youtube"))

    for p in session.exec(
        select(InstagramPost).where(
            InstagramPost.is_sponsored == True,  # noqa: E712
            InstagramPost.brand_id.is_not(None),
            InstagramPost.creator_id.is_not(None),
        )
    ).all():
        edges.append(SponsorshipEdge(creator_id=p.creator_id, brand_id=p.brand_id, content_id=p.post_id, platform="instagram"))

    for r in session.exec(
        select(RedditPost).where(
            RedditPost.is_sponsored == True,  # noqa: E712
            RedditPost.brand_id.is_not(None),
            RedditPost.creator_id.is_not(None),
        )
    ).all():
        edges.append(SponsorshipEdge(creator_id=r.creator_id, brand_id=r.brand_id, content_id=r.post_id, platform="reddit"))

    return edges

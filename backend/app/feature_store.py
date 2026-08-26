"""DB -> feature-store pipeline (PROJECT_PLAN.md Section 6, Weeks 5-6).

Transforms Track A's raw ingested tables into the shape Track B's GAIL
branch (`ml/schema.py` on track-b-ml-core) and Track C's own scoring logic
need to consume. Deliberately does NOT compute CLIP/BERT embeddings itself
-- that's Track B's Weeks 9-10 deliverable (confirmed via
GRAPH_SCHEMA.md's "What Track A needs to produce" section and
PROJECT_PLAN.md Section 6 row 9-10, which assigns "Run CLIP + BERT feature
extraction across dataset" to Track B, not Track C). This module stages the
text/thumbnail inputs those embeddings need -- text scrubbed per Section 2
(`app/text_processing.py::scrub_text`, added Weeks 7-8) so Track B gets
cleaner BERT input -- plus the numeric/categorical metadata segment of
Track B's creator feature vector (`ml/schema.py` CREATOR_METADATA_DIM =
log_subscriber_count + engagement_rate + reputation_score + category
one-hot) that doesn't require a trained model to compute.

Known gaps, flagged rather than fabricated:
- `reputation_score`: Track B's ml/schema.py expects this in the metadata
  segment, but no Track A table has a reputation_score source column
  anywhere (re-checked 2026-08-10 against Track A's latest work -- still
  true). Always None here until a real source is defined -- open
  cross-track item, see API_CONTRACTS.md.
- `sponsors`/`sponsored_by` edges depend on `is_sponsored` being populated
  -- that's `app/labeling.py`, added Weeks 7-8. Run `POST /labeling/run`
  before expecting non-empty sponsorship edges.

`co_occurs_with` edges (platform co-occurrence, PROJECT_PLAN.md Section
3a) are now REAL, added 2026-08-10: Track A added `reddit_post_creators`
(a many-to-many junction -- a Reddit post can relate to multiple creators,
most commonly because `creators.reddit_handles` is often a shared
community subreddit like r/badminton, not creator-exclusive). Two creators
linked to the same post is genuine content co-occurrence. Confirmed real,
not just schema: as of 2026-08-10 there are 5 real posts linking PV Sindhu
and Saina Nehwal via r/badminton.
"""

import itertools
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
    RedditPostCreator,
    YouTubeChannel,
    YouTubeVideo,
)
from app.schemas import CollaborationEdge, CreatorFeatureRecord, SponsorshipEdge
from app.text_processing import scrub_text

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
        raw_text = scrub_text(" ".join(raw_text_parts))

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

    Ambiguous handles (the same normalized handle claimed by 2+ creator
    rows) are treated as unresolvable, not resolved to whichever creator
    happened to be seen last while building the lookup map. This matters
    for real, not just hypothetical, reasons: confirmed live on 2026-08-09
    that Track A's pre-fix creator-dedup bug (see their "Fix cross-platform
    creator-ID syncing" commit) left real duplicate rows in production --
    two separate `creators` rows both claiming reddit handle "lebron". Their
    fix stops new duplicates but doesn't retroactively merge old ones, so
    this code can't assume handles are unique across creators even after
    the fix landed. Silently picking one would produce a real, wrong edge
    the moment creator_related_accounts starts getting populated for
    affected creators (empty today, so not yet actually wrong -- but it
    would have been the next time someone touched this code without
    checking, so fixed now instead of leaving it as a landmine).
    """
    creators = session.exec(select(Creator)).all()
    if not creators:
        return []

    # Two-pass: collect every creator_id per normalized handle first, so we
    # can drop ambiguous (multi-owner) handles before doing any resolution.
    raw_handle_owners: dict[str, dict[str, set[uuid.UUID]]] = {
        "youtube": defaultdict(set), "instagram": defaultdict(set), "reddit": defaultdict(set)
    }
    for c in creators:
        if c.youtube_handle:
            raw_handle_owners["youtube"][_normalize_handle(c.youtube_handle)].add(c.creator_id)
        if c.instagram_handle:
            raw_handle_owners["instagram"][_normalize_handle(c.instagram_handle)].add(c.creator_id)
        for h in c.reddit_handles:
            raw_handle_owners["reddit"][_normalize_handle(h)].add(c.creator_id)

    handle_maps: dict[str, dict[str, uuid.UUID]] = {
        platform: {handle: owners.pop() for handle, owners in owners_by_handle.items() if len(owners) == 1}
        for platform, owners_by_handle in raw_handle_owners.items()
    }

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


def build_co_occurrence_edges(session: Session) -> list[CollaborationEdge]:
    """`(creator, co_occurs_with, creator)`, both directions, per Track B's
    ml/schema.py. Real signal added by Track A 2026-08-10:
    `reddit_post_creators` links a Reddit post to every creator it relates
    to (a post can relate to multiple creators when they share a community
    subreddit, e.g. r/badminton) -- two creators linked to the same post is
    genuine platform co-occurrence. Weight = number of distinct posts the
    pair co-occurs on.

    Returns `CollaborationEdge` (same shape as collaborates_with) since the
    wire shape is identical -- the edge *type* is what differs, and that's
    which endpoint/field this came from, not something encoded per-row.
    """
    pair_weights: dict[tuple[str, str], int] = defaultdict(int)

    creators_by_post: dict[str, set[uuid.UUID]] = defaultdict(set)
    for row in session.exec(select(RedditPostCreator)).all():
        creators_by_post[row.post_id].add(row.creator_id)

    for creator_ids in creators_by_post.values():
        if len(creator_ids) < 2:
            continue
        for a, b in itertools.combinations(sorted(creator_ids, key=str), 2):
            pair_weights[(str(a), str(b))] += 1

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

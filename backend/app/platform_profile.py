"""Per-platform status of a creator: audience, typical views / likes / comments, engagement and first-day growth on YouTube and on Instagram, side by side.

WHY (26 Oct 2026): a single score hides that a creator can be strong on one platform and weak on the other. A brand that wants a YouTube-led campaign can still pick a
creator who is quiet on Instagram. This module only describes what the collected data shows; it never invents a number: anything the data does not cover is None and
the platform says why in `notes`.

Status (strong / typical / weak) compares a creator's engagement rate with the other creators we track on that platform: top third, middle third, bottom third.
It needs at least MIN_ITEMS posts with counts, otherwise it is 'unknown'. Engagement rate: YouTube (likes + comments) / views of the creator's latest mature videos;
Instagram (likes + comments) / followers of the latest posts with counts.
"""
from __future__ import annotations

import statistics as st
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from app.models import InstagramPost, InstagramProfile, YouTubeChannel, YouTubeVideo
from app.schemas import FirstDayGrowth, PlatformProfile, PlatformSide

MIN_ITEMS = 5            # posts with counts needed before a status is given
RECENT_ITEMS = 20        # the latest items that describe "typical now"
MATURE_DAYS_YOUTUBE = 30  # younger videos are still collecting views
CACHE_SECONDS = 600
_cohort_cache: dict[str, tuple[float, list[float]]] = {}


def _aware(d: Optional[datetime]) -> Optional[datetime]:
    if d is None:
        return None
    if isinstance(d, str):   # raw SQL on SQLite (tests) returns text
        d = datetime.fromisoformat(d)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _median(xs: list[float]) -> Optional[float]:
    return float(st.median(xs)) if xs else None


def _status(rate: Optional[float], cohort: list[float]) -> tuple[str, Optional[float]]:
    """('strong' | 'typical' | 'weak' | 'unknown', percentile 0-100 among the cohort)."""
    if rate is None or len(cohort) < 10:
        return "unknown", None
    pct = 100.0 * sum(1 for c in cohort if c < rate) / len(cohort)
    return ("strong" if pct >= 66.7 else "weak" if pct < 33.3 else "typical"), round(pct, 1)


def _yt_rate(v: YouTubeVideo) -> Optional[float]:
    if not v.view_count or v.like_count is None or v.comment_count is None:
        return None
    return (v.like_count + v.comment_count) / v.view_count


def _youtube_cohort(session: Session, refresh: bool) -> list[float]:
    hit = _cohort_cache.get("youtube")
    if hit and not refresh and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    cutoff = datetime.now(timezone.utc) - timedelta(days=MATURE_DAYS_YOUTUBE)
    per: dict[uuid.UUID, list[tuple[datetime, float]]] = {}
    for cid, published, views, likes, comments in session.exec(
        select(YouTubeVideo.creator_id, YouTubeVideo.published_at, YouTubeVideo.view_count, YouTubeVideo.like_count, YouTubeVideo.comment_count).where(
            YouTubeVideo.creator_id.is_not(None), YouTubeVideo.view_count > 0, YouTubeVideo.like_count.is_not(None), YouTubeVideo.comment_count.is_not(None)
        )
    ).all():
        if published and _aware(published) <= cutoff:
            per.setdefault(cid, []).append((_aware(published), (likes + comments) / views))
    cohort = [st.median(r for _, r in sorted(v, reverse=True)[:RECENT_ITEMS]) for v in per.values() if len(v) >= MIN_ITEMS]
    _cohort_cache["youtube"] = (time.time(), cohort)
    return cohort


def _instagram_cohort(session: Session, refresh: bool) -> list[float]:
    hit = _cohort_cache.get("instagram")
    if hit and not refresh and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    followers = {u: f for u, f in session.exec(select(InstagramProfile.username, InstagramProfile.follower_count)).all() if f}
    per: dict[uuid.UUID, list[tuple[datetime, float]]] = {}
    for cid, user, posted, likes, comments in session.exec(
        select(InstagramPost.creator_id, InstagramPost.username, InstagramPost.posted_at, InstagramPost.like_count, InstagramPost.comment_count).where(
            InstagramPost.creator_id.is_not(None), InstagramPost.like_count.is_not(None), InstagramPost.comment_count.is_not(None)
        )
    ).all():
        if posted and followers.get(user):
            per.setdefault(cid, []).append((_aware(posted), (likes + comments) / followers[user]))
    cohort = [st.median(r for _, r in sorted(v, reverse=True)[:RECENT_ITEMS]) for v in per.values() if len(v) >= MIN_ITEMS]
    _cohort_cache["instagram"] = (time.time(), cohort)
    return cohort


def _first_day(session: Session, creator_id: uuid.UUID, platform: str, published: dict[str, datetime], current: dict[str, int]) -> Optional[FirstDayGrowth]:
    """Value of the growth reading closest to 24 h after posting (20-28 h) against the value now. YouTube counts views; Instagram counts likes."""
    column = "view_count" if platform == "youtube" else "like_count"
    try:
        rows = session.execute(
            text(f"select post_id, fetched_at, {column} from post_snapshots where platform = :p and creator_id = :c and {column} is not null"),
            {"p": platform, "c": str(creator_id)},
        ).all()
    except Exception:  # the table is not mapped by SQLModel and may not exist (tests, fresh database)
        session.rollback()
        return None
    best: dict[str, tuple[float, int]] = {}
    for post_id, fetched, value in rows:
        born = published.get(post_id)
        if born is None:
            continue
        age_h = (_aware(fetched) - born).total_seconds() / 3600
        if 20 <= age_h <= 28 and (post_id not in best or abs(age_h - 24) < best[post_id][0]):
            best[post_id] = (abs(age_h - 24), value)
    shares = [v / current[p] for p, (_, v) in best.items() if current.get(p) and v <= current[p]]   # a reading above the stored total means the counts disagree: not used
    if not best:
        return None
    return FirstDayGrowth(items_with_a_first_day_reading=len(best), median_value_at_24h=_median([v for _, v in best.values()]), median_share_of_current_total=_median(shares))


def youtube_side(session: Session, creator_id: uuid.UUID, refresh: bool = False) -> PlatformSide:
    channel = session.exec(select(YouTubeChannel).where(YouTubeChannel.creator_id == creator_id)).first()
    videos = session.exec(select(YouTubeVideo).where(YouTubeVideo.creator_id == creator_id)).all()
    side = PlatformSide(platform="youtube", available=bool(videos or channel), audience=channel.subscriber_count if channel else None, items_total=len(videos))
    if not side.available:
        side.notes.append("No YouTube data collected for this creator.")
        return side
    now = datetime.now(timezone.utc)
    dated = [v for v in videos if v.published_at]
    side.latest_item_at = max((_aware(v.published_at) for v in dated), default=None)
    side.items_last_90_days = sum(1 for v in dated if _aware(v.published_at) >= now - timedelta(days=90))
    mature = sorted((v for v in dated if _aware(v.published_at) <= now - timedelta(days=MATURE_DAYS_YOUTUBE) and v.view_count is not None), key=lambda v: _aware(v.published_at), reverse=True)
    side.items_with_counts = len(mature)
    recent = mature[:RECENT_ITEMS]
    side.typical_views = _median([v.view_count for v in recent])
    side.typical_likes = _median([v.like_count for v in recent if v.like_count is not None])
    side.typical_comments = _median([v.comment_count for v in recent if v.comment_count is not None])
    rate = _median([r for r in (_yt_rate(v) for v in recent) if r is not None])
    side.engagement_rate = rate
    if side.audience and side.typical_views:
        side.views_per_subscriber = side.typical_views / side.audience
    spons = [v.view_count for v in mature if v.is_sponsored]
    plain = [v.view_count for v in mature if v.is_sponsored is False or v.is_sponsored is None]
    if len(spons) >= 3 and len(plain) >= 5:
        side.sponsored_vs_usual = _median(spons) / max(_median(plain), 1)
    side.status, side.percentile = _status(rate if len(recent) >= MIN_ITEMS else None, _youtube_cohort(session, refresh))
    side.first_day = _first_day(session, creator_id, "youtube", {v.video_id: _aware(v.published_at) for v in dated}, {v.video_id: v.view_count for v in dated if v.view_count})
    if side.status == "unknown":
        side.notes.append(f"Fewer than {MIN_ITEMS} videos older than {MATURE_DAYS_YOUTUBE} days with counts, or too few creators to compare with.")
    if side.first_day is None:
        side.notes.append("No video of this creator has a growth reading about 24 hours after posting yet (readings only exist since 11 Oct 2026).")
    return side


def instagram_side(session: Session, creator_id: uuid.UUID, refresh: bool = False) -> PlatformSide:
    profile = session.exec(select(InstagramProfile).where(InstagramProfile.creator_id == creator_id)).first()
    posts = session.exec(select(InstagramPost).where(InstagramPost.creator_id == creator_id)).all()
    side = PlatformSide(platform="instagram", available=bool(posts or profile), audience=profile.follower_count if profile else None, items_total=len(posts))
    if not side.available:
        side.notes.append("No Instagram data collected for this creator.")
        return side
    now = datetime.now(timezone.utc)
    dated = [p for p in posts if p.posted_at]
    side.latest_item_at = max((_aware(p.posted_at) for p in dated), default=None)
    side.items_last_90_days = sum(1 for p in dated if _aware(p.posted_at) >= now - timedelta(days=90))
    counted = sorted((p for p in dated if p.like_count is not None and p.comment_count is not None), key=lambda p: _aware(p.posted_at), reverse=True)
    side.items_with_counts = len(counted)
    recent = counted[:RECENT_ITEMS]
    side.typical_likes = _median([p.like_count for p in recent])
    side.typical_comments = _median([p.comment_count for p in recent])
    rate = (_median([p.like_count + p.comment_count for p in recent]) / side.audience) if recent and side.audience else None
    side.engagement_rate = rate
    spons = [p.like_count + p.comment_count for p in counted if p.is_sponsored or p.has_paid_partnership_label]
    plain = [p.like_count + p.comment_count for p in counted if not (p.is_sponsored or p.has_paid_partnership_label)]
    if len(spons) >= 3 and len(plain) >= 5:
        side.sponsored_vs_usual = _median(spons) / max(_median(plain), 1)
    side.status, side.percentile = _status(rate if len(recent) >= MIN_ITEMS else None, _instagram_cohort(session, refresh))
    side.first_day = _first_day(session, creator_id, "instagram", {p.post_id: _aware(p.posted_at) for p in dated}, {p.post_id: p.like_count for p in dated if p.like_count})
    if len(posts) > len(counted):
        side.notes.append(f"Likes and comments are known for {len(counted)} of {len(posts)} collected posts.")
    if not side.audience:
        side.notes.append("Follower count not collected, so engagement rate cannot be computed.")
    if side.status == "unknown" and len(recent) < MIN_ITEMS:
        side.notes.append(f"Fewer than {MIN_ITEMS} posts with counts: status cannot be judged.")
    if side.first_day is None:
        side.notes.append("No post has a growth reading about 24 hours after posting yet.")
    return side


def build_profile(session: Session, creator_id: uuid.UUID, refresh: bool = False) -> PlatformProfile:
    yt, ig = youtube_side(session, creator_id, refresh), instagram_side(session, creator_id, refresh)
    rank = {"strong": 2, "typical": 1, "weak": 0}
    if yt.status in rank and ig.status in rank:
        if yt.status == ig.status:
            summary = f"About equally {yt.status} on YouTube and Instagram."
        else:
            hi, lo = (("YouTube", "Instagram") if rank[yt.status] > rank[ig.status] else ("Instagram", "YouTube"))
            summary = f"Stronger on {hi} than on {lo}: {hi} engagement is {max(yt.status, ig.status, key=rank.get)}, {lo} is {min(yt.status, ig.status, key=rank.get)}."
    elif yt.status in rank:
        summary = f"YouTube engagement is {yt.status}; Instagram cannot be judged from the data we have."
    elif ig.status in rank:
        summary = f"Instagram engagement is {ig.status}; YouTube cannot be judged from the data we have."
    else:
        summary = "Not enough data on either platform to judge engagement."
    return PlatformProfile(creator_id=creator_id, summary=summary, youtube=yt, instagram=ig)


def warm_up() -> None:
    """Fill the comparison data in the background at startup, so the first request is not slow (about 9 s on the full database)."""
    import threading

    def run() -> None:
        from app.database import engine

        try:
            with Session(engine) as session:
                _youtube_cohort(session, True)
                _instagram_cohort(session, True)
        except Exception:  # best effort: the first request computes it itself
            pass

    threading.Thread(target=run, daemon=True).start()

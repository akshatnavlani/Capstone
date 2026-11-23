"""Per-platform status of creators: YouTube and Instagram side by side (see app/platform_profile.py)."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models import Creator, InstagramPost, YouTubeVideo
from app.platform_profile import build_profile
from app.schemas import PlatformProfile

router = APIRouter(prefix="/platform-profiles", tags=["platform-profiles"])


@router.get("/{creator_id}", response_model=PlatformProfile)
def get_platform_profile(creator_id: uuid.UUID, refresh: bool = False, session: Session = Depends(get_session)) -> PlatformProfile:
    if session.get(Creator, creator_id) is None:
        raise HTTPException(status_code=404, detail="creator not found")
    return build_profile(session, creator_id, refresh)


@router.get("/{creator_id}/timeline")
def get_timeline(creator_id: uuid.UUID, limit: int = Query(20, ge=3, le=60), session: Session = Depends(get_session)) -> dict:
    """23 Nov 2026, for the line charts in the brand report: the creator's latest YouTube videos (at least 7 days old, so
    views have settled) and latest Instagram posts, oldest first. Read-only; raw counts, nothing estimated."""
    if session.get(Creator, creator_id) is None:
        raise HTTPException(status_code=404, detail="creator not found")
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    yt = session.exec(
        select(YouTubeVideo)
        .where(YouTubeVideo.creator_id == creator_id, YouTubeVideo.published_at.is_not(None), YouTubeVideo.published_at <= cutoff, YouTubeVideo.view_count.is_not(None))
        .order_by(YouTubeVideo.published_at.desc())
        .limit(limit)
    ).all()
    ig = session.exec(
        select(InstagramPost)
        .where(InstagramPost.creator_id == creator_id, InstagramPost.posted_at.is_not(None), InstagramPost.like_count.is_not(None))
        .order_by(InstagramPost.posted_at.desc())
        .limit(limit)
    ).all()
    return {
        "creator_id": str(creator_id),
        "youtube": [{"at": v.published_at.isoformat(), "views": v.view_count, "sponsored": bool(v.is_sponsored)} for v in reversed(yt)],
        "instagram": [{"at": p.posted_at.isoformat(), "likes": p.like_count, "sponsored": bool(p.is_sponsored)} for p in reversed(ig)],
    }


@router.get("", response_model=list[PlatformProfile])
def get_platform_profiles(creator_ids: list[uuid.UUID] = Query(..., max_length=50), session: Session = Depends(get_session)) -> list[PlatformProfile]:
    """Several creators at once (the dashboard asks for the creators of one result list). Unknown ids are skipped."""
    return [build_profile(session, cid) for cid in creator_ids if session.get(Creator, cid) is not None]

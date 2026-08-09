"""Runs the disclosure-tag labeling pipeline (app/labeling.py) against
content rows where is_sponsored is still null, and persists the result.

Track A's real orchestrator writes new content directly to Postgres (see
API_CONTRACTS.md breaking-change note #3), so this endpoint is meant to be
invoked periodically/on-demand (manually for now) to catch up rows Track A
has landed since the last run -- there's no trigger/webhook wiring it
automatically yet.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import require_api_key
from app.database import get_session
from app.labeling import detect_sponsorship
from app.models import InstagramPost, RedditPost, YouTubeVideo
from app.schemas import LabelingPlatformResult, LabelingRunResponse

router = APIRouter(prefix="/labeling", tags=["labeling"])


@router.post("/run", response_model=LabelingRunResponse, dependencies=[Depends(require_api_key)])
def run_labeling(session: Session = Depends(get_session)) -> LabelingRunResponse:
    yt_checked = yt_sponsored = 0
    for v in session.exec(select(YouTubeVideo).where(YouTubeVideo.is_sponsored.is_(None))).all():
        found, matches = detect_sponsorship(v.title, v.description)
        v.is_sponsored = found
        v.sponsorship_raw_matches = matches or None
        session.add(v)
        yt_checked += 1
        yt_sponsored += int(found)

    ig_checked = ig_sponsored = 0
    for p in session.exec(select(InstagramPost).where(InstagramPost.is_sponsored.is_(None))).all():
        found, matches = detect_sponsorship(p.caption)
        p.is_sponsored = found
        p.sponsorship_raw_matches = matches or None
        session.add(p)
        ig_checked += 1
        ig_sponsored += int(found)

    rd_checked = rd_sponsored = 0
    for r in session.exec(select(RedditPost).where(RedditPost.is_sponsored.is_(None))).all():
        found, matches = detect_sponsorship(r.title, r.body)
        r.is_sponsored = found
        r.sponsorship_raw_matches = matches or None
        session.add(r)
        rd_checked += 1
        rd_sponsored += int(found)

    session.commit()

    return LabelingRunResponse(
        youtube_videos=LabelingPlatformResult(checked=yt_checked, labeled_sponsored=yt_sponsored),
        instagram_posts=LabelingPlatformResult(checked=ig_checked, labeled_sponsored=ig_sponsored),
        reddit_posts=LabelingPlatformResult(checked=rd_checked, labeled_sponsored=rd_sponsored),
    )

"""Runs the disclosure-tag labeling pipeline (app/labeling.py) against
content rows, and persists the result.

Track A's real orchestrator writes new content directly to Postgres (see
API_CONTRACTS.md breaking-change note #3), so this endpoint is meant to be
invoked periodically/on-demand (manually for now) to catch up rows Track A
has landed since the last run -- there's no trigger/webhook wiring it
automatically yet.

Default mode only processes `is_sponsored IS NULL` rows (cheap, safe to
call often). `force=True` reprocesses every row regardless of current
value -- needed because Track A's upsert only touches columns *they* write
(caption/title/body etc.), never `is_sponsored`/`sponsorship_raw_matches`
(that's Track C's column). So if Track A corrects/refetches a row's text
after it was already labeled (e.g. the 2026-08-10 caption-truncation fix),
the corrected text silently never gets re-examined under the default mode
-- the row is no longer null, so it's permanently skipped even though the
label was computed against now-stale text. Found via the Kohli/Agilitas
case: labeled `false` against a truncated caption, and the default mode
would never re-check it even after Track A fixes the truncation.
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
def run_labeling(force: bool = False, session: Session = Depends(get_session)) -> LabelingRunResponse:
    yt_checked = yt_sponsored = 0
    yt_query = select(YouTubeVideo) if force else select(YouTubeVideo).where(YouTubeVideo.is_sponsored.is_(None))
    for v in session.exec(yt_query).all():
        found, matches = detect_sponsorship(v.title, v.description)
        v.is_sponsored = found
        v.sponsorship_raw_matches = matches or None
        session.add(v)
        yt_checked += 1
        yt_sponsored += int(found)

    ig_checked = ig_sponsored = 0
    ig_query = select(InstagramPost) if force else select(InstagramPost).where(InstagramPost.is_sponsored.is_(None))
    for p in session.exec(ig_query).all():
        found, matches = detect_sponsorship(p.caption)
        # Instagram's own "Paid partnership" declaration is a native,
        # high-confidence signal independent of (and not always present in)
        # caption text -- e.g. collab posts with no caption at all still
        # carry it. Treat it as sponsored regardless of the text match.
        if p.has_paid_partnership_label:
            found = True
            matches = matches + ["native:paid_partnership_label"]
        p.is_sponsored = found
        p.sponsorship_raw_matches = matches or None
        session.add(p)
        ig_checked += 1
        ig_sponsored += int(found)

    rd_checked = rd_sponsored = 0
    rd_query = select(RedditPost) if force else select(RedditPost).where(RedditPost.is_sponsored.is_(None))
    for r in session.exec(rd_query).all():
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

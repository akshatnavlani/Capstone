"""Secondary/manual write path into the shared Supabase schema Track A owns.

NOTE (2026-08-09): Track A's real ingestion orchestrator writes directly to
Postgres via DATABASE_URL (scripts/ingestion/orchestrator.py on
track-a-data-infra), bypassing this API entirely. These endpoints exist for
manual testing / other tracks seeding data, not as the primary pipeline --
see API_CONTRACTS.md.

All endpoints accept a batch (list) and upsert by the real table's primary
key (channel_id / video_id / username / post_id / creator_id). is_sponsored
and sponsorship_raw_matches are optional everywhere: neither Track A nor
Track C currently populates them (the disclosure-tag labeling pipeline is
Track C's Weeks 7-8 deliverable) -- omit them or pass null.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Creator,
    InstagramPost,
    InstagramProfile,
    RedditPost,
    RedditProfile,
    YouTubeChannel,
    YouTubeVideo,
)
from app.schemas import (
    CreatorIngest,
    IngestionResponse,
    InstagramPostIngest,
    InstagramProfileIngest,
    RedditPostIngest,
    RedditProfileIngest,
    YouTubeChannelIngest,
    YouTubeVideoIngest,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _upsert_by_pk(session: Session, model, pk_field: str, payload: list) -> IngestionResponse:
    created = updated = 0
    for item in payload:
        data = item.model_dump()
        pk_value = data[pk_field]
        existing = session.get(model, pk_value)

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            session.add(existing)
            updated += 1
        else:
            session.add(model(**data))
            created += 1

    session.commit()
    return IngestionResponse(received=len(payload), created=created, updated=updated)


@router.post("/creators", response_model=IngestionResponse)
def ingest_creators(payload: list[CreatorIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    created = updated = 0
    for item in payload:
        data = item.model_dump()
        creator_id = data.get("creator_id") or uuid.uuid4()
        data["creator_id"] = creator_id

        existing = session.get(Creator, creator_id)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            session.add(existing)
            updated += 1
        else:
            session.add(Creator(**data))
            created += 1

    session.commit()
    return IngestionResponse(received=len(payload), created=created, updated=updated)


@router.post("/youtube/channels", response_model=IngestionResponse)
def ingest_youtube_channels(payload: list[YouTubeChannelIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_by_pk(session, YouTubeChannel, "channel_id", payload)


@router.post("/youtube/videos", response_model=IngestionResponse)
def ingest_youtube_videos(payload: list[YouTubeVideoIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_by_pk(session, YouTubeVideo, "video_id", payload)


@router.post("/instagram/profiles", response_model=IngestionResponse)
def ingest_instagram_profiles(payload: list[InstagramProfileIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_by_pk(session, InstagramProfile, "username", payload)


@router.post("/instagram/posts", response_model=IngestionResponse)
def ingest_instagram_posts(payload: list[InstagramPostIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_by_pk(session, InstagramPost, "post_id", payload)


@router.post("/reddit/profiles", response_model=IngestionResponse)
def ingest_reddit_profiles(payload: list[RedditProfileIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_by_pk(session, RedditProfile, "username", payload)


@router.post("/reddit/posts", response_model=IngestionResponse)
def ingest_reddit_posts(payload: list[RedditPostIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_by_pk(session, RedditPost, "post_id", payload)

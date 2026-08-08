"""Endpoints Track A's data pipeline calls to write scraped/processed data.

All endpoints accept a batch (list) and upsert by natural key:
- Creators: unique_id
- Platform posts: (creator_unique_id, platform_post_id)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import Creator, InstagramPost, RedditPost, YouTubePost
from app.schemas import (
    CreatorIngest,
    InstagramPostIngest,
    IngestionResponse,
    RedditPostIngest,
    YouTubePostIngest,
)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/creators", response_model=IngestionResponse)
def ingest_creators(payload: list[CreatorIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    created = updated = 0
    for item in payload:
        existing = session.exec(select(Creator).where(Creator.unique_id == item.unique_id)).first()
        data = item.model_dump()
        data["related_accounts"] = ",".join(item.related_accounts) if item.related_accounts else None
        data["prior_endorsements"] = ",".join(item.prior_endorsements) if item.prior_endorsements else None

        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            session.add(existing)
            updated += 1
        else:
            session.add(Creator(**data))
            created += 1

    session.commit()
    return IngestionResponse(received=len(payload), created=created, updated=updated)


def _upsert_posts(session: Session, model, payload: list, key_field: str) -> IngestionResponse:
    created = updated = 0
    for item in payload:
        existing = session.exec(
            select(model).where(
                model.creator_unique_id == item.creator_unique_id,
                model.platform_post_id == item.platform_post_id,
            )
        ).first()
        data = item.model_dump()

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


@router.post("/youtube", response_model=IngestionResponse)
def ingest_youtube(payload: list[YouTubePostIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_posts(session, YouTubePost, payload, "platform_post_id")


@router.post("/instagram", response_model=IngestionResponse)
def ingest_instagram(payload: list[InstagramPostIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_posts(session, InstagramPost, payload, "platform_post_id")


@router.post("/reddit", response_model=IngestionResponse)
def ingest_reddit(payload: list[RedditPostIngest], session: Session = Depends(get_session)) -> IngestionResponse:
    return _upsert_posts(session, RedditPost, payload, "platform_post_id")

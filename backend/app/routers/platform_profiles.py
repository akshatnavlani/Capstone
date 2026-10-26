"""Per-platform status of creators: YouTube and Instagram side by side (see app/platform_profile.py)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.database import get_session
from app.models import Creator
from app.platform_profile import build_profile
from app.schemas import PlatformProfile

router = APIRouter(prefix="/platform-profiles", tags=["platform-profiles"])


@router.get("/{creator_id}", response_model=PlatformProfile)
def get_platform_profile(creator_id: uuid.UUID, refresh: bool = False, session: Session = Depends(get_session)) -> PlatformProfile:
    if session.get(Creator, creator_id) is None:
        raise HTTPException(status_code=404, detail="creator not found")
    return build_profile(session, creator_id, refresh)


@router.get("", response_model=list[PlatformProfile])
def get_platform_profiles(creator_ids: list[uuid.UUID] = Query(..., max_length=50), session: Session = Depends(get_session)) -> list[PlatformProfile]:
    """Several creators at once (the dashboard asks for the creators of one result list). Unknown ids are skipped."""
    return [build_profile(session, cid) for cid in creator_ids if session.get(Creator, cid) is not None]

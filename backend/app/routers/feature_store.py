"""Read-only endpoints over app/feature_store.py -- lets Track B (or anyone)
inspect the DB -> feature-store transformation over HTTP without needing a
local DB connection. See feature_store.py for the transformation logic and
the remaining known gap (reputation_score).
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import feature_store
from app.database import get_session
from app.schemas import CollaborationEdge, CreatorFeatureRecord, SponsorshipEdge

router = APIRouter(prefix="/feature-store", tags=["feature-store"])


@router.get("/creators", response_model=list[CreatorFeatureRecord])
def get_creator_features(session: Session = Depends(get_session)) -> list[CreatorFeatureRecord]:
    return feature_store.build_creator_features(session)


@router.get("/edges/collaborations", response_model=list[CollaborationEdge])
def get_collaboration_edges(session: Session = Depends(get_session)) -> list[CollaborationEdge]:
    return feature_store.build_collaboration_edges(session)


@router.get("/edges/sponsorships", response_model=list[SponsorshipEdge])
def get_sponsorship_edges(session: Session = Depends(get_session)) -> list[SponsorshipEdge]:
    return feature_store.build_sponsorship_edges(session)


@router.get("/edges/co-occurrence", response_model=list[CollaborationEdge])
def get_co_occurrence_edges(session: Session = Depends(get_session)) -> list[CollaborationEdge]:
    return feature_store.build_co_occurrence_edges(session)

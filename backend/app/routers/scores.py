"""Fusion Layer score endpoint (PROJECT_PLAN.md Section 4).

Once ML-Core (Track B) has real GAIL/Temporal branch outputs, they call
POST /scores/compute with those values; this stores and returns the fused
0-100 score. GET retrieves the most recently computed score for a creator.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import require_api_key
from app.config import settings
from app.database import get_session
from app.fusion import compute_fusion_score
from app.models import FusionScore
from app.schemas import FusionScoreComputeRequest, FusionScoreResponse, ScoreBreakdown

router = APIRouter(prefix="/scores", tags=["scores"])


@router.post("/compute", response_model=FusionScoreResponse, dependencies=[Depends(require_api_key)])
def compute_score(payload: FusionScoreComputeRequest, session: Session = Depends(get_session)) -> FusionScoreResponse:
    final_score, confidence_low, confidence_high, risk_adjustment, breakdown = compute_fusion_score(
        payload.spillover_score, payload.sentiment_risk_score, payload.creator_feature_score
    )

    record = FusionScore(
        creator_id=payload.creator_id,
        spillover_score=payload.spillover_score,
        sentiment_risk_score=payload.sentiment_risk_score,
        creator_feature_score=payload.creator_feature_score,
        final_score=final_score,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        risk_adjustment=risk_adjustment,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    return FusionScoreResponse(
        creator_id=record.creator_id,
        final_score=record.final_score,
        confidence_low=record.confidence_low,
        confidence_high=record.confidence_high,
        risk_adjustment=record.risk_adjustment,
        breakdown=breakdown,
        computed_at=record.computed_at,
        is_placeholder_formula=True,
    )


@router.get("/{creator_id}", response_model=FusionScoreResponse)
def get_latest_score(creator_id: uuid.UUID, session: Session = Depends(get_session)) -> FusionScoreResponse:
    record = session.exec(
        select(FusionScore)
        .where(FusionScore.creator_id == creator_id)
        .order_by(FusionScore.computed_at.desc())
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"No fusion score found for creator '{creator_id}'")

    breakdown = ScoreBreakdown(
        spillover_score=record.spillover_score,
        sentiment_risk_score=record.sentiment_risk_score,
        creator_feature_score=record.creator_feature_score,
        weight_spillover=settings.fusion_weight_spillover,
        weight_sentiment_risk=settings.fusion_weight_sentiment_risk,
        weight_creator_feature=settings.fusion_weight_creator_feature,
    )

    return FusionScoreResponse(
        creator_id=record.creator_id,
        final_score=record.final_score,
        confidence_low=record.confidence_low,
        confidence_high=record.confidence_high,
        risk_adjustment=record.risk_adjustment,
        breakdown=breakdown,
        computed_at=record.computed_at,
        is_placeholder_formula=True,
    )

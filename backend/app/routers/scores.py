"""Fusion Layer score endpoint (PROJECT_PLAN.md Section 4).

POST /scores/compute now auto-resolves spillover_score via GAIL checkpoint
(c6488a6) when caller omits it — otherwise uses caller-supplied value.
GET recomputes live spillover so Track D sees honest basis + wide CI.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import require_api_key
from app.config import settings
from app.database import get_session
from app.fusion import PLACEHOLDER_CONFIDENCE_MARGIN, compute_fusion_score
from app.models import FusionScore
from app.schemas import FusionScoreComputeRequest, FusionScoreResponse, ScoreBreakdown
from app.spillover import PLACEHOLDER_HALF_WIDTH, get_spillover

router = APIRouter(prefix="/scores", tags=["scores"])


@router.post("/compute", response_model=FusionScoreResponse, dependencies=[Depends(require_api_key)])
def compute_score(payload: FusionScoreComputeRequest, session: Session = Depends(get_session)) -> FusionScoreResponse:
    # Auto-resolve spillover if caller omitted it — real GAIL if available, else placeholder
    if payload.spillover_score is None:
        sp = get_spillover(payload.creator_id)
        spillover_score = sp["spillover_score"]
        basis = sp["basis"]
        hw = abs(sp["confidence_high"] - sp["spillover_score"])
    else:
        spillover_score = payload.spillover_score
        # Caller supplied explicit score — treat as trained if within GAIL range,
        # but basis is caller-asserted; mark as placeholder for honesty
        basis = "placeholder"
        hw = None

    final_score, confidence_low, confidence_high, risk_adjustment, breakdown = compute_fusion_score(
        spillover_score,
        payload.sentiment_risk_score,
        payload.creator_feature_score,
        spillover_half_width=hw,
        spillover_basis=basis,
    )

    record = FusionScore(
        creator_id=payload.creator_id,
        spillover_score=spillover_score,
        spillover_basis=basis,
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
        spillover_basis=basis,  # type: ignore[arg-type]
        computed_at=record.computed_at,
        is_placeholder_formula=True,
    )


@router.get("/{creator_id}", response_model=FusionScoreResponse)
def get_latest_score(creator_id: uuid.UUID, session: Session = Depends(get_session)) -> FusionScoreResponse:
    # Live spillover: recompute from GAIL so basis/CI reflect current checkpoint,
    # not stale DB row. Fallback to stored row if no history — but still try GAIL.
    sp = get_spillover(creator_id)
    live_spillover = sp["spillover_score"]
    live_basis = sp["basis"]
    live_hw = abs(sp["confidence_high"] - live_spillover)

    record = session.exec(
        select(FusionScore)
        .where(FusionScore.creator_id == creator_id)
        .order_by(FusionScore.computed_at.desc())
    ).first()

    if record:
        # Recompute fusion with live spillover but keep stored sentiment/creator_feature
        final_score, confidence_low, confidence_high, risk_adjustment, breakdown = compute_fusion_score(
            live_spillover,
            record.sentiment_risk_score,
            record.creator_feature_score,
            spillover_half_width=live_hw,
            spillover_basis=live_basis,
        )
        return FusionScoreResponse(
            creator_id=creator_id,
            final_score=final_score,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
            risk_adjustment=risk_adjustment,
            breakdown=breakdown,
            spillover_basis=live_basis,  # type: ignore[arg-type]
            computed_at=record.computed_at,
            is_placeholder_formula=True,
        )

    # No stored row — compute on-the-fly with live spillover + placeholder other scores
    # (w2/w3 still 0.5 placeholder per CAPSTONE_NEXT_STEPS.md:822)
    final_score, confidence_low, confidence_high, risk_adjustment, breakdown = compute_fusion_score(
        live_spillover, 0.5, 0.5, spillover_half_width=live_hw, spillover_basis=live_basis
    )
    from datetime import datetime, timezone

    return FusionScoreResponse(
        creator_id=creator_id,
        final_score=final_score,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        risk_adjustment=risk_adjustment,
        breakdown=breakdown,
        spillover_basis=live_basis,  # type: ignore[arg-type]
        computed_at=datetime.now(timezone.utc),
        is_placeholder_formula=True,
    )

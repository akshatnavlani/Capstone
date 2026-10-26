"""Monitoring/alerts endpoint (PROJECT_PLAN.md Section 5).

Risk flags are fed by Track B's sentiment propagation output later; for now
POST lets any track push a flag manually, and GET is what the frontend
polls for the monitoring dashboard.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import require_api_key
from app.database import get_session
from app.models import Creator, RiskAlert
from app.schemas import AlertCreate, AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("", response_model=AlertResponse, dependencies=[Depends(require_api_key)])
def create_alert(payload: AlertCreate, session: Session = Depends(get_session)) -> AlertResponse:
    record = RiskAlert(**payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return AlertResponse(**record.model_dump())


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    creator_id: Optional[uuid.UUID] = None,
    include_resolved: bool = False,
    session: Session = Depends(get_session),
) -> list[AlertResponse]:
    query = select(RiskAlert)
    if creator_id:
        query = query.where(RiskAlert.creator_id == creator_id)
    if not include_resolved:
        query = query.where(RiskAlert.resolved == False)  # noqa: E712

    records = session.exec(query.order_by(RiskAlert.created_at.desc())).all()
    wanted = {r.creator_id for r in records} | {r.propagated_from_creator_id for r in records if r.propagated_from_creator_id}
    names = {c.creator_id: c.name for c in session.exec(select(Creator).where(Creator.creator_id.in_(wanted))).all()} if wanted else {}
    return [
        AlertResponse(**r.model_dump(), creator_name=names.get(r.creator_id), propagated_from_name=names.get(r.propagated_from_creator_id))
        for r in records
    ]

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.config import settings
from app.database import get_session
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(session: Session = Depends(get_session)) -> HealthResponse:
    try:
        session.exec(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    return HealthResponse(status="ok", db_connected=db_connected, version=settings.api_version)

"""What-if spillover scenario: real graph and real current sponsorships with an assumed strength (see app/spillover_scenario.py). Read only; never changes a score."""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas import SpilloverScenario
from app.spillover_scenario import MAX_EFFECT_LOG, build_scenario

router = APIRouter(prefix="/scenario", tags=["scenario"])


@router.get("/spillover", response_model=SpilloverScenario)
def get_spillover_scenario(effect: float = Query(0.5, ge=0.0, le=MAX_EFFECT_LOG, description="Assumed spillover strength on the log scale; 0.5 is about +65% for a fully exposed creator"),
                           session: Session = Depends(get_session)) -> SpilloverScenario:
    return SpilloverScenario(**build_scenario(session, effect))

"""Creator Passport endpoints (see app/passport.py). Read-only; nothing here changes a score."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import insights, passport

router = APIRouter(prefix="/passport", tags=["passport"])


def _need(value, what: str):
    if value is None:
        raise HTTPException(status_code=503, detail=f"{what} not built yet: run scripts/build_creator_passport.py")
    return value


@router.get("/summary")
def get_summary() -> dict:
    """Group-level result of each novelty analysis, with its placebo or leave-one-out check and the limits."""
    return _need(passport.summary(), "the passport file")


@router.get("/insights")
def get_insights() -> dict:
    """Chart data for the Insights page: the spillover journey, benchmark errors, power curve and the Passport distributions. Read-only; every block names its source file."""
    return insights.build()


@router.get("/strip")
def get_strip(ids: list[str] = Query(..., max_length=50)) -> dict:
    """Compact Passport facts for a list of creators (the dashboard cards ask for the creators of one result list)."""
    _need(passport.summary(), "the passport file")
    return passport.strip(ids)


@router.get("/creators")
def get_creators() -> list[dict]:
    """Light list for search: id, name, category, evidence grade and two flags."""
    return passport.creator_list()


@router.get("/clash")
def get_clash(product: str = Query(..., min_length=1, max_length=200), brand: Optional[str] = Query(None, max_length=100)) -> dict:
    """Creators who recently promoted a rival brand in the brief's category (competitor-clash flag). A warning only; scores are unchanged."""
    _need(passport.summary(), "the passport file")
    return passport.clash(product, brand)


@router.get("/{creator_id}")
def get_passport(creator_id: str) -> dict:
    _need(passport.summary(), "the passport file")
    record = passport.get_creator(creator_id)
    if record is None:
        raise HTTPException(status_code=404, detail="creator not found")
    return record

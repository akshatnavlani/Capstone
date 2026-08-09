import math

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import alerts, feature_store, health, influencers, ingestion, scores

app = FastAPI(title=settings.api_title, version=settings.api_version)


def _sanitize_non_finite(obj):
    """Replace NaN/Infinity with their repr so error responses stay JSON-serializable.

    Starlette's JSONResponse renders with allow_nan=False (spec-compliant JSON has
    no NaN/Infinity token). FastAPI's default validation-error handler echoes the
    raw invalid input back in the error body -- if a client sends e.g.
    `"budget": NaN`, that raw float ends up in the 422 body and crashes the
    encoder with an unhandled 500 instead of returning the 422. Found via
    adversarial testing on 2026-08-09; this sanitizes recursively so it holds for
    any endpoint/field, not just the one that surfaced it.
    """
    if isinstance(obj, float) and not math.isfinite(obj):
        return repr(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_non_finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_non_finite(v) for v in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": _sanitize_non_finite(exc.errors())})


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(health.router)
app.include_router(influencers.router)
app.include_router(ingestion.router)
app.include_router(scores.router)
app.include_router(alerts.router)
app.include_router(feature_store.router)

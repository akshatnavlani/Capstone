from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.routers import alerts, health, influencers, ingestion, scores

app = FastAPI(title=settings.api_title, version=settings.api_version)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(health.router)
app.include_router(influencers.router)
app.include_router(ingestion.router)
app.include_router(scores.router)
app.include_router(alerts.router)

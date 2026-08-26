from sqlmodel import SQLModel, Session, create_engine

from app.config import settings
from app.models import TRACK_C_OWNED_TABLES

IS_SQLITE = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


def init_db() -> None:
    """Create tables if missing.

    Against real Postgres: only Track C's own tables (FusionScore,
    RiskAlert). Track A owns migrations for creators/youtube_*/instagram_*/
    reddit_* (see SCHEMA.md on track-a-data-infra) -- those already exist in
    the real Supabase instance and must never be auto-created/altered here.

    Against the local SQLite dev fallback: the full metadata, including
    Track A-mirrored tables. SQLite is never Track A's real environment, so
    creating a local copy here is safe -- and necessary, since otherwise
    those tables wouldn't exist at all locally and any query against them
    would raise instead of `/recommendations` falling through to its
    mock-data path.
    """
    if IS_SQLITE:
        SQLModel.metadata.create_all(engine)
    else:
        SQLModel.metadata.create_all(engine, tables=TRACK_C_OWNED_TABLES)


def get_session():
    with Session(engine) as session:
        yield session

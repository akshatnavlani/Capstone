from sqlmodel import SQLModel, Session, create_engine

from app.config import settings
from app.models import TRACK_C_OWNED_TABLES

IS_SQLITE = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}
# Supabase's pooler closes idle connections; without a check the first request after a quiet period failed with "server closed the connection unexpectedly" (seen 1 Nov 2026).
# pool_pre_ping tests a pooled connection before use and replaces a dead one; pool_recycle retires connections after 5 minutes. Postgres only.
pool_kwargs = {} if IS_SQLITE else {"pool_pre_ping": True, "pool_recycle": 300}
engine = create_engine(settings.database_url, connect_args=connect_args, **pool_kwargs)


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

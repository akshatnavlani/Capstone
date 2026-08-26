from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment / .env file.

    DATABASE_URL defaults to a local SQLite file so the API runs standalone
    before Track A hands off the Supabase Postgres connection string. Swap
    it for the Postgres URL (postgresql+psycopg2://...) once available --
    no code changes needed elsewhere.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./fusion_backend.db"

    # Shared-secret API key for write endpoints (ingestion, scores/compute,
    # POST /alerts). Unset (None/empty) = auth disabled -- local dev stays
    # frictionless by default. Set API_KEY in .env to enable; callers send
    # it as the X-API-Key header. Deliberately basic (one shared secret, no
    # per-track keys/roles) -- flagged as missing twice, closing the gap
    # now rather than letting it become real technical debt, but full
    # per-track auth is out of scope for a 4-person thesis capstone backend.
    api_key: Optional[str] = None

    # Fusion Layer weights (PROJECT_PLAN.md Section 4):
    # final_score = w1*spillover + w2*sentiment_risk + w3*creator_feature
    # Placeholder values until calibrated against held-out historical outcomes.
    fusion_weight_spillover: float = 0.4
    fusion_weight_sentiment_risk: float = 0.3
    fusion_weight_creator_feature: float = 0.3

    api_title: str = "Capstone Fusion Backend"
    api_version: str = "0.1.0"

    # Comma-separated allowed origins for CORS -- defaults to Track D's
    # Next.js dev server (`next dev` defaults to port 3000; both
    # localhost/127.0.0.1 listed since browsers treat them as distinct
    # origins for CORS purposes). No CORSMiddleware existed at all before
    # 2026-08-10 -- curl doesn't enforce/send Origin the way a real browser
    # does, so every prior "verified end-to-end" check across every track
    # missed this; found by Track D's first real browser test. Extend via
    # CORS_ALLOW_ORIGINS in .env (comma-separated) once there's a deployed
    # frontend origin to add.
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()

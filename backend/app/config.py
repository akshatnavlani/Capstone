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
    # 30 Oct 2026: spillover lowered 0.4 -> 0.2 (sentiment and feature 0.3 -> 0.4 each): the real-data spillover test found nothing and the held-out check did not beat
    # simple baselines, so the branch gets less say until it is validated. scripts/calibrate_fusion.py shows how far the ranking moves.
    # 1 Nov 2026: spillover taken OUT of the score (0.0; sentiment and feature 0.5 each). The real-data spillover estimate is a bounded null (+0.01, 95% -0.55 to +0.33 on 74 exposed observations), so the branch should not
    # move a ranking. It is still computed and shown on every card as context. scripts/simulate_fusion.py: with no spillover signal the ranking is unchanged (Spearman 0.356 vs 0.354); if spillover DID carry signal
    # (0.5) keeping it would help (0.401 vs 0.358), which the real data does not support. Set FUSION_WEIGHT_SPILLOVER=0.2, FUSION_WEIGHT_SENTIMENT_RISK=0.4, FUSION_WEIGHT_CREATOR_FEATURE=0.4 in .env to restore the 30 Oct priors.
    fusion_weight_spillover: float = 0.0
    fusion_weight_sentiment_risk: float = 0.5
    fusion_weight_creator_feature: float = 0.5

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

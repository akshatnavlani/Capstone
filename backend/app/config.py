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

    # Fusion Layer weights (PROJECT_PLAN.md Section 4):
    # final_score = w1*spillover + w2*sentiment_risk + w3*creator_feature
    # Placeholder values until calibrated against held-out historical outcomes.
    fusion_weight_spillover: float = 0.4
    fusion_weight_sentiment_risk: float = 0.3
    fusion_weight_creator_feature: float = 0.3

    api_title: str = "Capstone Fusion Backend"
    api_version: str = "0.1.0"


settings = Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_url: str = "postgresql://ap_user:ap_password@localhost:5432/ap_db"
    redis_url: str = "redis://localhost:6379/0"

    # Alert engine behaviour
    poll_interval_secs: int = 10          # how often to check for ungrouped anomalies
    grouping_window_secs: int = 600       # anomalies within 10 min → same incident
    suppression_window_secs: int = 300    # don't re-fire for same series within 5 min

    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()

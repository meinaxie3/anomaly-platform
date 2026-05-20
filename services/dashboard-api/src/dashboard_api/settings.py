"""Dashboard API settings — loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_url: str = "postgresql://ap_user:ap_password@localhost:5432/ap_db"
    port: int = 8003

    # Maximum age of the `from` query param (guards against full-table scans)
    max_window_days: int = 30

    # Default look-back when no ?from is supplied
    default_window_hours: int = 3

    # Threshold (hours) above which the API reads metrics_1min instead of raw metrics
    aggregate_threshold_hours: float = 2.0

    # Hard cap on rows returned to the browser per metric series
    max_raw_points: int = 500


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_url: str = "postgresql://ap_user:ap_password@localhost:5432/ap_db"

    # MinIO / S3
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "models"

    # Training window
    training_window_days: int = 30
    holdout_fraction: float = 0.2  # last 20% of window reserved for eval

    # Isolation Forest
    contamination: float = 0.05  # expected anomaly rate

    # Scheduler — run at this UTC hour nightly
    schedule_hour: int = 2

    # Logging
    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()

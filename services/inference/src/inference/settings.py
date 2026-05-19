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

    # Scoring
    # Isolation Forest decision_function: scores below threshold → anomaly.
    # 0.0 is the natural decision boundary; nudge negative to reduce false positives.
    inference_threshold: float = 0.0

    # Model cache TTL — reload from MinIO after this many seconds
    model_ttl_seconds: int = 300

    # Server
    host: str = "0.0.0.0"
    port: int = 8002

    # Logging
    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()

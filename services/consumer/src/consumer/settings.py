from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str = "redis://localhost:6379/0"
    stream_name: str = "metrics:stream"
    consumer_group: str = "consumer-group"
    consumer_name: str = "consumer-1"
    batch_size: int = 100
    block_ms: int = 2000

    postgres_url: str = "postgresql://ap_user:ap_password@localhost:5432/ap_db"
    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    port: int = 8001
    log_level: str = "INFO"
    env: str = "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()

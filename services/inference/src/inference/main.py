"""Inference service entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ap_logging import get_logger
from inference.model_cache import ModelCache
from inference.routes import router
from inference.settings import Settings, get_settings
from training.store import ModelStore

log = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    pool_override: asyncpg.Pool | None = None,
    cache_override: ModelCache | None = None,
) -> FastAPI:
    """Factory — accepts overrides for testing without live infrastructure."""
    _settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = pool_override or await asyncpg.create_pool(
            _settings.postgres_url, min_size=1, max_size=8
        )
        store = ModelStore(
            endpoint=_settings.minio_endpoint,
            access_key=_settings.minio_access_key,
            secret_key=_settings.minio_secret_key,
            bucket=_settings.minio_bucket,
        )
        cache = cache_override or ModelCache(
            store=store,
            pool=pool,
            ttl_seconds=_settings.model_ttl_seconds,
        )
        app.state.pool = pool
        app.state.model_cache = cache
        app.state.settings = _settings
        log.info("inference_service_started", port=_settings.port)
        yield
        if pool_override is None:
            await pool.close()

    app = FastAPI(
        title="Anomaly Inference Service",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return app


def main() -> None:
    settings = get_settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

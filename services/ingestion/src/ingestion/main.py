from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from ap_logging import configure_logging, get_logger
from fastapi import FastAPI

from ingestion.routes import router
from ingestion.settings import get_settings


def create_app(redis_override: aioredis.Redis | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings = get_settings()
        configure_logging("ingestion", settings.env, settings.log_level)
        log = get_logger(__name__)

        client: aioredis.Redis
        if redis_override is not None:
            client = redis_override
        else:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)

        app.state.redis = client
        log.info("redis_connected", url=settings.redis_url)
        yield
        if redis_override is None:
            await client.aclose()
            log.info("redis_closed")

    app = FastAPI(
        title="Anomaly Platform — Ingestion API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("ingestion.main:app", host="0.0.0.0", port=settings.port, reload=True)

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import redis.asyncio as aioredis
from ap_logging import configure_logging, get_logger
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from ingestion.metrics import stream_depth
from ingestion.routes import router
from ingestion.settings import get_settings

_DEPTH_POLL_INTERVAL = 15  # seconds between XLEN polls


async def _poll_stream_depth(client: aioredis.Redis, stream: str) -> None:
    """Background task: update the stream-depth gauge every poll interval."""
    log = get_logger(__name__)
    while True:
        try:
            depth = await client.xlen(stream)
            stream_depth.set(depth)
        except Exception as exc:
            log.warning("stream_depth_poll_failed", error=str(exc))
        await asyncio.sleep(_DEPTH_POLL_INTERVAL)


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

        poller = asyncio.create_task(
            _poll_stream_depth(client, settings.stream_name),
            name="stream-depth-poller",
        )
        yield

        poller.cancel()
        with suppress(asyncio.CancelledError):
            await poller

        if redis_override is None:
            await client.aclose()
            log.info("redis_closed")

    app = FastAPI(
        title="Anomaly Platform -- Ingestion API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)

    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run("ingestion.main:app", host="0.0.0.0", port=settings.port, reload=True)

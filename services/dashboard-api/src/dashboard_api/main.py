"""Dashboard API entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg
import uvicorn
from ap_logging import get_logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from dashboard_api.routes import router
from dashboard_api.settings import Settings, get_settings

log = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings: Settings = app.state.settings
    log.info("dashboard_api_starting", port=settings.port)

    pool = await asyncpg.create_pool(settings.postgres_url, min_size=2, max_size=10)
    app.state.pool = pool
    log.info("db_pool_created")

    yield

    await pool.close()
    log.info("dashboard_api_stopped")


def create_app(
    settings: Settings | None = None,
    pool_override: asyncpg.Pool | None = None,
) -> FastAPI:
    """Factory used in production and in tests (pool_override skips live DB)."""
    resolved_settings = settings or get_settings()

    app = FastAPI(
        title="Anomaly Platform — Dashboard API",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.state.settings = resolved_settings

    if pool_override is not None:
        # Tests inject a mock pool; bypass the lifespan DB setup
        app.state.pool = pool_override
        # Replace lifespan with a no-op so TestClient doesn't create a real pool
        app.router.lifespan_context = _noop_lifespan  # type: ignore[assignment,unused-ignore]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:4173",  # Vite preview
        ],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(router)
    Instrumentator().instrument(app).expose(app)

    return app


@asynccontextmanager
async def _noop_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "dashboard_api.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()

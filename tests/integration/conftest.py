"""
Shared fixtures for integration tests.

Prerequisites: `make up` must be running before executing these tests.
Run with: uv run pytest -m integration --tb=short
"""

import asyncio
import os
import uuid

import asyncpg
import pytest
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://ap_user:ap_password@localhost:5432/ap_db",
)
INGESTION_URL = os.getenv("INGESTION_URL", "http://localhost:8001")


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.DefaultEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
async def pg_pool() -> asyncpg.Pool:
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=4)
    yield pool  # type: ignore[misc]
    await pool.close()


@pytest.fixture(scope="session")
async def redis_client() -> aioredis.Redis:
    client = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield client  # type: ignore[misc]
    await client.aclose()


@pytest.fixture()
def unique_stream(request: pytest.FixtureRequest) -> str:
    """Return a per-test unique stream name to prevent cross-test pollution."""
    return f"test:metrics:{uuid.uuid4().hex[:8]}"

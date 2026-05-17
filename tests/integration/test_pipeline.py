"""
End-to-end pipeline integration tests.

These tests require all infrastructure to be running:
    make up

Run with:
    uv run pytest -m integration --tb=short

They are excluded from the default `pytest` run and from CI unless
a separate job with `docker compose` services is added.
"""

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import httpx
import pytest
import redis.asyncio as aioredis

from tests.integration.conftest import INGESTION_URL

pytestmark = pytest.mark.integration


def _event_payload(**kwargs) -> dict:  # type: ignore[type-arg]
    defaults = dict(
        service="payment-api",
        metric="cpu_percent",
        value=42.5,
        timestamp=datetime.now(tz=UTC).isoformat(),
    )
    return {**defaults, **kwargs}


# ── Ingestion API ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingestion_health_endpoint() -> None:
    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingestion_metrics_endpoint() -> None:
    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "ingestion_stream_depth" in resp.text


@pytest.mark.asyncio
async def test_single_event_accepted_by_api() -> None:
    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        resp = await client.post("/ingest", json=_event_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert "event_id" in body


@pytest.mark.asyncio
async def test_batch_ingest_accepted_by_api() -> None:
    events = [_event_payload(value=float(i)) for i in range(10)]
    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        resp = await client.post("/ingest/batch", json=events)
    assert resp.status_code == 202
    assert resp.json()["count"] == 10


@pytest.mark.asyncio
async def test_invalid_payload_rejected_with_422() -> None:
    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        resp = await client.post("/ingest", json={"service": "x"})
    assert resp.status_code == 422


# ── Redis stream ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_lands_in_redis_stream(redis_client: aioredis.Redis) -> None:
    event_id = str(uuid4())
    payload = _event_payload(event_id=event_id)

    before = await redis_client.xlen("metrics:stream")

    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        await client.post("/ingest", json=payload)

    after = await redis_client.xlen("metrics:stream")
    assert after > before


@pytest.mark.asyncio
async def test_batch_increases_stream_depth(redis_client: aioredis.Redis) -> None:
    before = await redis_client.xlen("metrics:stream")
    events = [_event_payload(value=float(i)) for i in range(50)]

    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        await client.post("/ingest/batch", json=events)

    after = await redis_client.xlen("metrics:stream")
    assert after >= before + 50


# ── End-to-end: API -> Redis -> Consumer -> TimescaleDB ──────────────────────


@pytest.mark.asyncio
async def test_single_event_lands_in_timescale(pg_pool: asyncpg.Pool) -> None:
    """POST one event, wait up to 10s for the consumer to write it."""
    event_id = str(uuid4())
    payload = _event_payload(event_id=event_id)

    async with httpx.AsyncClient(base_url=INGESTION_URL) as client:
        resp = await client.post("/ingest", json=payload)
    assert resp.status_code == 202

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT event_id FROM metrics WHERE event_id = $1::uuid",
                event_id,
            )
        if row is not None:
            break
        await asyncio.sleep(0.5)

    assert row is not None, f"Event {event_id} never appeared in TimescaleDB within 10s"


@pytest.mark.asyncio
async def test_batch_idempotency(pg_pool: asyncpg.Pool) -> None:
    """POST the same 10 events twice; the table must contain exactly 10 rows."""
    events = [_event_payload(event_id=str(uuid4()), value=float(i)) for i in range(10)]
    event_ids = [e["event_id"] for e in events]

    async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=15.0) as client:
        await client.post("/ingest/batch", json=events)
        await client.post("/ingest/batch", json=events)  # duplicate

    # Wait for the consumer
    await asyncio.sleep(8.0)

    async with pg_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM metrics WHERE event_id = ANY($1::uuid[])",
            event_ids,
        )

    assert count == 10, f"Expected 10 unique rows, got {count}"


@pytest.mark.asyncio
async def test_stream_depth_recovers_after_consumer_drains(
    redis_client: aioredis.Redis,
) -> None:
    """Send 500 events and verify XLEN eventually returns to 0 (consumer drains fully)."""
    events = [_event_payload(value=float(i % 100)) for i in range(500)]

    async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=30.0) as client:
        # Split into 5 batches of 100 to stay under default batch limit
        for i in range(0, 500, 100):
            await client.post("/ingest/batch", json=events[i : i + 100])

    deadline = time.monotonic() + 30.0
    depth = await redis_client.xlen("metrics:stream")
    while depth > 0 and time.monotonic() < deadline:
        await asyncio.sleep(1.0)
        depth = await redis_client.xlen("metrics:stream")

    assert depth == 0, f"Stream still has {depth} messages after 30s"

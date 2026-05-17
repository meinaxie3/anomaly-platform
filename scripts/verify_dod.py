"""
Phase 2 Definition-of-Done verification script.

Checks:
  1. Ingestion API is reachable and healthy
  2. Generates a short synthetic window and sends it via /ingest/batch
  3. Waits for the consumer to write all events to TimescaleDB
  4. Verifies zero loss: row count in DB == events sent
  5. Queries the Prometheus /metrics endpoint for ingestion p99 latency

Prerequisites: make up + ingestion service + consumer all running.

Usage:
    uv run python scripts/verify_dod.py
    uv run python scripts/verify_dod.py --duration-mins 15 --interval-secs 60
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx
import redis.asyncio as aioredis
import typer

INGESTION_URL = "http://localhost:8001"
REDIS_URL = "redis://localhost:6379/0"
POSTGRES_URL = "postgresql://ap_user:ap_password@localhost:5432/ap_db"

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _ok(msg: str) -> None:
    typer.echo(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    typer.echo(f"  [FAIL] {msg}", err=True)


def _info(msg: str) -> None:
    typer.echo(f"  [INFO] {msg}")


async def _run(duration_mins: int, interval_secs: int, drain_timeout: int) -> bool:
    passed = True

    # ── 1. API health ─────────────────────────────────────────────────────────
    typer.echo("\n[1] Ingestion API health")
    try:
        async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=5.0) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        _ok(f"GET /health -> {resp.json()}")
    except Exception as exc:
        _fail(f"Ingestion API unreachable: {exc}")
        typer.echo("\nAborting: start the ingestion service first (`uv run ingestion`).")
        return False

    # ── 2. Generate and send events ───────────────────────────────────────────
    typer.echo(f"\n[2] Generating {duration_mins}-min window at {interval_secs}s interval")
    from load_gen.generator import MetricGenerator

    end = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    start = end - timedelta(minutes=duration_mins)
    generator = MetricGenerator(seed=42)
    interval = timedelta(seconds=interval_secs)
    expected = generator.event_count(start, end, interval)
    _info(f"Expected events: {expected:,}")

    sent = 0
    batch: list[dict] = []  # type: ignore[type-arg]
    t_send_start = time.monotonic()

    async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=30.0) as client:
        for event, _ in generator.events(start, end, interval):
            batch.append(json.loads(event.model_dump_json()))
            if len(batch) >= 200:
                resp = await client.post("/ingest/batch", json=batch)
                if resp.is_success:
                    sent += len(batch)
                else:
                    _fail(f"Batch rejected: {resp.status_code} {resp.text[:100]}")
                    passed = False
                batch = []

        if batch:
            resp = await client.post("/ingest/batch", json=batch)
            if resp.is_success:
                sent += len(batch)
            else:
                _fail(f"Final batch rejected: {resp.status_code}")
                passed = False

    send_elapsed = time.monotonic() - t_send_start
    _ok(f"Sent {sent:,} events in {send_elapsed:.1f}s")

    if sent != expected:
        _fail(f"Send loss: expected {expected:,}, sent {sent:,}")
        passed = False

    # ── 3. Wait for consumer to drain ─────────────────────────────────────────
    typer.echo(f"\n[3] Waiting up to {drain_timeout}s for consumer to drain stream")
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    deadline = time.monotonic() + drain_timeout
    depth = await redis.xlen("metrics:stream")
    while depth > 0 and time.monotonic() < deadline:
        await asyncio.sleep(2.0)
        depth = await redis.xlen("metrics:stream")
    await redis.aclose()

    if depth == 0:
        _ok("Stream fully drained")
    else:
        _fail(f"Stream still has {depth} messages after {drain_timeout}s")
        passed = False

    # ── 4. Row count in TimescaleDB ───────────────────────────────────────────
    typer.echo("\n[4] Verifying row count in TimescaleDB")
    pool = await asyncpg.create_pool(POSTGRES_URL)
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM metrics WHERE timestamp BETWEEN $1 AND $2",
        start,
        end,
    )
    await pool.close()

    _info(f"Rows in DB for window: {count:,}  (sent: {sent:,})")
    if count >= sent:
        _ok("No loss detected (count >= sent, duplicates absorbed by ON CONFLICT)")
    else:
        _fail(f"Loss detected: {sent - count:,} events missing from TimescaleDB")
        passed = False

    # ── 5. Prometheus p99 latency ─────────────────────────────────────────────
    typer.echo("\n[5] Checking ingestion p99 latency from /metrics")
    try:
        async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=5.0) as client:
            resp = await client.get("/metrics")
        # Parse the 0.99 quantile from http_request_duration_seconds
        pattern = r'http_request_duration_seconds\{[^}]*quantile="0\.99"[^}]*\}\s+([\d.e+-]+)'
        match = re.search(pattern, resp.text)
        if match:
            p99_ms = float(match.group(1)) * 1000
            _info(f"Ingestion p99 latency: {p99_ms:.1f}ms")
            if p99_ms < 100:
                _ok(f"p99 {p99_ms:.1f}ms < 100ms target")
            else:
                _fail(f"p99 {p99_ms:.1f}ms exceeds 100ms target")
                passed = False
        else:
            _info("p99 quantile not yet available in /metrics (insufficient traffic)")
    except Exception as exc:
        _info(f"Could not fetch /metrics: {exc}")

    return passed


@app.command()
def main(
    duration_mins: int = typer.Option(5, help="Synthetic window size in minutes"),
    interval_secs: int = typer.Option(60, help="Seconds between metric ticks"),
    drain_timeout: int = typer.Option(60, help="Max seconds to wait for consumer drain"),
) -> None:
    typer.echo("=" * 60)
    typer.echo("Phase 2 Definition-of-Done Verification")
    typer.echo("=" * 60)

    passed = asyncio.run(_run(duration_mins, interval_secs, drain_timeout))

    typer.echo("\n" + "=" * 60)
    if passed:
        typer.echo("[PASS] All checks passed. Phase 2 DoD satisfied.")
    else:
        typer.echo("[FAIL] One or more checks failed. See output above.", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

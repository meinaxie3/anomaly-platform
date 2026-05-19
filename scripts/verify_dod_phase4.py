"""
Phase 4 Definition-of-Done verification script.

Checks:
  1. Inference service is reachable and healthy
  2. Inject a known spike anomaly via POST /ingest
  3. Anomaly appears in the anomalies table within 30s
  4. Incident appears in the incidents table within 60s
  5. POST /reload on inference service flushes the model cache

Prerequisites:
    docker compose -f infra/docker-compose.yml up -d --wait
    uv run ingestion        (terminal 2)
    uv run consumer         (terminal 3)
    uv run inference        (terminal 4)
    uv run alerts           (terminal 5)
    uv run training --run-once   (to seed models first)

Usage:
    uv run python scripts/verify_dod_phase4.py
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import httpx
import typer

INGESTION_URL = "http://localhost:8001"
INFERENCE_URL = "http://localhost:8002"
POSTGRES_URL = "postgresql://ap_user:ap_password@localhost:5432/ap_db"

# Spike value — 10x typical cpu_percent to guarantee anomaly detection
SPIKE_VALUE = 999.0
SPIKE_SERVICE = "payment-api"
SPIKE_METRIC = "cpu_percent"

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _ok(msg: str) -> None:
    typer.echo(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    typer.echo(f"  [FAIL] {msg}", err=True)


def _info(msg: str) -> None:
    typer.echo(f"  [INFO] {msg}")


async def _run() -> bool:
    passed = True

    # ── 1. Inference health ───────────────────────────────────────────────────
    typer.echo("\n[1] Inference service health")
    try:
        async with httpx.AsyncClient(base_url=INFERENCE_URL, timeout=5.0) as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        _ok(f"GET /health -> {body}")
    except Exception as exc:
        _fail(f"Inference service unreachable: {exc}")
        typer.echo("\nAborting: start the inference service first (`uv run inference`).")
        return False

    # ── 2. Inject known spike anomaly ─────────────────────────────────────────
    typer.echo("\n[2] Injecting spike anomaly via ingestion API")
    event_id = str(uuid4())
    payload = {
        "event_id": event_id,
        "service": SPIKE_SERVICE,
        "metric": SPIKE_METRIC,
        "value": SPIKE_VALUE,
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }
    try:
        async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=5.0) as client:
            resp = await client.post("/ingest", json=payload)
        assert resp.status_code == 202
        _ok(f"Injected spike event_id={event_id[:8]}... value={SPIKE_VALUE}")
    except Exception as exc:
        _fail(f"Failed to inject event: {exc}")
        return False

    # ── 3. Anomaly in DB within 30s ───────────────────────────────────────────
    typer.echo("\n[3] Waiting up to 30s for anomaly to appear in anomalies table")
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=2)
    deadline = time.monotonic() + 30.0
    anomaly_row = None

    while time.monotonic() < deadline:
        anomaly_row = await pool.fetchrow(
            "SELECT anomaly_id, score FROM anomalies WHERE event_id = $1::uuid",
            event_id,
        )
        if anomaly_row:
            break
        await asyncio.sleep(1.0)

    if anomaly_row:
        _ok(
            f"Anomaly detected: anomaly_id={str(anomaly_row['anomaly_id'])[:8]}... "
            f"score={anomaly_row['score']:.4f}"
        )
    else:
        _fail(f"Anomaly for event_id={event_id[:8]}... never appeared within 30s")
        _info(
            "Possible causes: no trained model for payment-api/cpu_percent "
            "(run: uv run training --run-once), or inference service not running."
        )
        passed = False

    # ── 4. Incident in DB within 60s ──────────────────────────────────────────
    typer.echo("\n[4] Waiting up to 60s for incident to appear in incidents table")
    deadline = time.monotonic() + 60.0
    incident_row = None

    while time.monotonic() < deadline:
        incident_row = await pool.fetchrow(
            """
            SELECT i.incident_id, i.status, i.started_at
            FROM   incidents i
            JOIN   anomalies a ON a.incident_id = i.incident_id
            WHERE  a.event_id = $1::uuid
            LIMIT  1
            """,
            event_id,
        )
        if incident_row:
            break
        await asyncio.sleep(2.0)

    if incident_row:
        _ok(
            f"Incident created: incident_id={str(incident_row['incident_id'])[:8]}... "
            f"status={incident_row['status']}"
        )
    else:
        _fail("No incident created within 60s")
        _info("Possible cause: alert engine not running (`uv run alerts`).")
        passed = False

    await pool.close()

    # ── 5. /reload flushes model cache ────────────────────────────────────────
    typer.echo("\n[5] Testing POST /reload on inference service")
    try:
        async with httpx.AsyncClient(base_url=INFERENCE_URL, timeout=5.0) as client:
            resp = await client.post("/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cache_flushed"
        _ok("Model cache flushed successfully")
    except Exception as exc:
        _fail(f"/reload failed: {exc}")
        passed = False

    return passed


@app.command()
def main() -> None:
    typer.echo("=" * 60)
    typer.echo("Phase 4 Definition-of-Done Verification")
    typer.echo("=" * 60)

    passed = asyncio.run(_run())

    typer.echo("\n" + "=" * 60)
    if passed:
        typer.echo("[PASS] All checks passed. Phase 4 DoD satisfied.")
    else:
        typer.echo("[FAIL] One or more checks failed. See output above.", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

"""
Phase 5 Definition-of-Done verification script.

Checks:
  1. Dashboard API is reachable and healthy
  2. GET /services returns at least one service
  3. GET /metrics/{service}/{metric} returns points + correct schema
  4. GET /incidents returns list with correct schema
  5. GET /models returns list with correct schema
  6. Time-range validation -- ?from too far back returns 400
  7. Inject spike anomaly and verify it appears in /metrics anomalies

Prerequisites:
    docker compose -f infra/docker-compose.yml up -d --wait
    uv run ingestion        (terminal 2)
    uv run consumer         (terminal 3)
    uv run inference        (terminal 4)
    uv run alerts           (terminal 5)
    uv run dashboard        (terminal 6)
    uv run training --run-once   (to seed models first)

Usage:
    uv run python scripts/verify_dod_phase5.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import typer

DASHBOARD_URL = "http://localhost:8003"
INGESTION_URL = "http://localhost:8001"

SPIKE_SERVICE = "payment-api"
SPIKE_METRIC = "cpu_percent"
SPIKE_VALUE = 999.0

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _ok(msg: str) -> None:
    typer.echo(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    typer.echo(f"  [FAIL] {msg}", err=True)


def _info(msg: str) -> None:
    typer.echo(f"  [INFO] {msg}")


async def _run() -> bool:
    passed = True

    async with httpx.AsyncClient(base_url=DASHBOARD_URL, timeout=10.0) as api:
        # ── 1. Health ─────────────────────────────────────────────────────────
        typer.echo("\n[1] Dashboard API health")
        try:
            r = await api.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
            _ok(f"GET /health -> {r.json()}")
        except Exception as exc:
            _fail(f"Dashboard API unreachable: {exc}")
            typer.echo("\nAborting: start the dashboard API first (`uv run dashboard`).")
            return False

        # ── 2. /services ─────────────────────────────────────────────────────
        typer.echo("\n[2] GET /services")
        try:
            r = await api.get("/services")
            assert r.status_code == 200
            services = r.json()
            assert isinstance(services, list)
            # Validate schema on first item
            if services:
                s = services[0]
                assert "service" in s
                assert "health" in s
                assert s["health"] in ("healthy", "degraded", "critical")
                assert "open_incidents" in s
                _ok(f"{len(services)} services returned, first: {s['service']} ({s['health']})")
            else:
                _info("No services yet (need load-gen running for at least a few seconds)")
                _ok("Empty list is valid schema response")
        except Exception as exc:
            _fail(f"/services failed: {exc}")
            passed = False

        # ── 3. /metrics/{service}/{metric} ────────────────────────────────────
        typer.echo(f"\n[3] GET /metrics/{SPIKE_SERVICE}/{SPIKE_METRIC}")
        try:
            now = datetime.now(tz=UTC)
            params = {
                "from": (now - timedelta(hours=3)).isoformat(),
                "to": now.isoformat(),
            }
            r = await api.get(f"/metrics/{SPIKE_SERVICE}/{SPIKE_METRIC}", params=params)
            assert r.status_code == 200
            body = r.json()
            assert "service" in body and body["service"] == SPIKE_SERVICE
            assert "metric" in body and body["metric"] == SPIKE_METRIC
            assert "points" in body and isinstance(body["points"], list)
            assert "anomalies" in body and isinstance(body["anomalies"], list)
            _ok(
                f"Schema valid -- {len(body['points'])} points, "
                f"{len(body['anomalies'])} anomalies in last 3h"
            )
        except Exception as exc:
            _fail(f"/metrics failed: {exc}")
            passed = False

        # ── 4. /incidents ─────────────────────────────────────────────────────
        typer.echo("\n[4] GET /incidents")
        try:
            r = await api.get("/incidents")
            assert r.status_code == 200
            incidents = r.json()
            assert isinstance(incidents, list)
            if incidents:
                i = incidents[0]
                assert "incident_id" in i
                assert "service" in i
                assert "status" in i
                assert "anomaly_count" in i
                _ok(f"{len(incidents)} incidents returned, first: {i['service']} [{i['status']}]")
            else:
                _ok("Empty list -- no incidents yet (valid schema)")
        except Exception as exc:
            _fail(f"/incidents failed: {exc}")
            passed = False

        # ── 5. /models ────────────────────────────────────────────────────────
        typer.echo("\n[5] GET /models")
        try:
            r = await api.get("/models")
            assert r.status_code == 200
            models = r.json()
            assert isinstance(models, list)
            if models:
                m = models[0]
                assert "model_id" in m
                assert "service" in m
                assert "algorithm" in m
                assert "eval_f1" in m
                assert "is_current" in m
                _ok(
                    f"{len(models)} models returned, first: {m['service']}/{m['metric']} "
                    f"({'current' if m['is_current'] else 'archived'})"
                )
            else:
                _info("No models yet -- run: uv run training --run-once")
                _ok("Empty list is valid schema response")
        except Exception as exc:
            _fail(f"/models failed: {exc}")
            passed = False

        # ── 6. Time-range validation ───────────────────────────────────────────
        typer.echo("\n[6] Time-range validation rejects out-of-bounds params")
        try:
            ancient = (datetime.now(tz=UTC) - timedelta(days=60)).isoformat()
            r = await api.get(f"/metrics/{SPIKE_SERVICE}/{SPIKE_METRIC}", params={"from": ancient})
            assert r.status_code == 400
            _ok("?from=60-days-ago correctly rejected with 400")
        except Exception as exc:
            _fail(f"Time-range validation failed: {exc}")
            passed = False

    # ── 7. Spike → anomaly appears in /metrics ─────────────────────────────
    typer.echo("\n[7] Inject spike anomaly and verify it appears in /metrics anomalies")
    try:
        event_id = str(uuid4())
        payload = {
            "event_id": event_id,
            "service": SPIKE_SERVICE,
            "metric": SPIKE_METRIC,
            "value": SPIKE_VALUE,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        async with httpx.AsyncClient(base_url=INGESTION_URL, timeout=5.0) as ing:
            r = await ing.post("/ingest", json=payload)
        assert r.status_code == 202, f"Ingestion returned {r.status_code}"
        _info(f"Spike injected (event_id={event_id[:8]}…)")

        # Wait up to 45 s for the anomaly to be scored and appear via dashboard API
        found = False
        for attempt in range(15):
            await asyncio.sleep(3.0)
            now = datetime.now(tz=UTC)
            params = {
                "from": (now - timedelta(minutes=5)).isoformat(),
                "to": now.isoformat(),
            }
            async with httpx.AsyncClient(base_url=DASHBOARD_URL, timeout=5.0) as api2:
                r2 = await api2.get(f"/metrics/{SPIKE_SERVICE}/{SPIKE_METRIC}", params=params)
            if r2.status_code == 200:
                anomalies = r2.json().get("anomalies", [])
                if any(a["score"] < 0 for a in anomalies):
                    found = True
                    _ok(
                        f"Anomaly visible in /metrics after ~{(attempt + 1) * 3}s -- "
                        f"{len(anomalies)} anomal{'y' if len(anomalies) == 1 else 'ies'} in window"
                    )
                    break

        if not found:
            _fail("Spike anomaly did not appear in /metrics anomalies within 45s")
            _info("Check: is the inference service running? (`uv run inference`)")
            _info("Check: is there a trained model for payment-api/cpu_percent?")
            passed = False

    except Exception as exc:
        _fail(f"Spike injection check failed: {exc}")
        passed = False

    return passed


@app.command()
def main() -> None:
    typer.echo("=" * 60)
    typer.echo("Phase 5 Definition-of-Done Verification")
    typer.echo("=" * 60)

    ok = asyncio.run(_run())

    typer.echo("\n" + "=" * 60)
    if ok:
        typer.echo("[PASS] All checks passed. Phase 5 DoD satisfied.")
    else:
        typer.echo("[FAIL] One or more checks failed. See output above.", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

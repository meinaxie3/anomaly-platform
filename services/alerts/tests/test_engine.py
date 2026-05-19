"""Unit tests for the alert engine cycle — all I/O mocked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from ap_schemas import AnomalyRecord
from alerts.engine import run_alert_cycle
from alerts.settings import Settings

BASE_TIME = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        postgres_url="postgresql://x:x@localhost/x",
        redis_url="redis://localhost:6379/0",
        poll_interval_secs=10,
        grouping_window_secs=600,
        suppression_window_secs=300,
    )


def _anomaly(service: str = "payment-api", metric: str = "cpu_percent") -> AnomalyRecord:
    return AnomalyRecord(
        event_id=uuid4(),
        service=service,
        metric=metric,
        value=500.0,
        score=-0.3,
        threshold=0.0,
        model_id="model-1",
        timestamp=BASE_TIME,
    )


@pytest.mark.asyncio
async def test_cycle_creates_incident_for_ungrouped_anomalies() -> None:
    pool = MagicMock()
    redis = AsyncMock()

    with (
        patch("alerts.engine.db.fetch_ungrouped_anomalies", new=AsyncMock(return_value=[_anomaly()])),
        patch("alerts.engine.db.persist_incident", new=AsyncMock()),
        patch("alerts.engine.suppression.is_suppressed", new=AsyncMock(return_value=False)),
        patch("alerts.engine.suppression.mark_fired", new=AsyncMock()),
    ):
        created, suppressed = await run_alert_cycle(pool, redis, _settings())

    assert created == 1
    assert suppressed == 0


@pytest.mark.asyncio
async def test_cycle_suppresses_when_already_fired() -> None:
    pool = MagicMock()
    redis = AsyncMock()

    with (
        patch("alerts.engine.db.fetch_ungrouped_anomalies", new=AsyncMock(return_value=[_anomaly()])),
        patch("alerts.engine.db.persist_incident", new=AsyncMock()) as mock_persist,
        patch("alerts.engine.suppression.is_suppressed", new=AsyncMock(return_value=True)),
        patch("alerts.engine.suppression.mark_fired", new=AsyncMock()),
    ):
        created, suppressed = await run_alert_cycle(pool, redis, _settings())

    assert created == 0
    assert suppressed == 1
    mock_persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_cycle_noop_when_no_anomalies() -> None:
    pool = MagicMock()
    redis = AsyncMock()

    with (
        patch("alerts.engine.db.fetch_ungrouped_anomalies", new=AsyncMock(return_value=[])),
        patch("alerts.engine.db.persist_incident", new=AsyncMock()) as mock_persist,
    ):
        created, suppressed = await run_alert_cycle(pool, redis, _settings())

    assert created == 0
    assert suppressed == 0
    mock_persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_cycle_separate_series_each_fire_independently() -> None:
    pool = MagicMock()
    redis = AsyncMock()
    anomalies = [
        _anomaly(service="payment-api", metric="cpu_percent"),
        _anomaly(service="auth-service", metric="latency_p99"),
    ]

    with (
        patch("alerts.engine.db.fetch_ungrouped_anomalies", new=AsyncMock(return_value=anomalies)),
        patch("alerts.engine.db.persist_incident", new=AsyncMock()),
        patch("alerts.engine.suppression.is_suppressed", new=AsyncMock(return_value=False)),
        patch("alerts.engine.suppression.mark_fired", new=AsyncMock()),
    ):
        created, suppressed = await run_alert_cycle(pool, redis, _settings())

    assert created == 2
    assert suppressed == 0

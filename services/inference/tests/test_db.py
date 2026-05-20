"""Unit tests for the anomaly DB writer — asyncpg is fully mocked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ap_schemas import AnomalyRecord
from inference.db import batch_insert_anomalies


def _anomaly(**overrides: object) -> AnomalyRecord:
    defaults = dict(
        event_id=uuid4(),
        service="payment-api",
        metric="cpu_percent",
        value=500.0,
        score=-0.25,
        threshold=0.0,
        model_id="model-abc",
        timestamp=datetime.now(tz=UTC),
    )
    defaults.update(overrides)
    return AnomalyRecord(**defaults)  # type: ignore[arg-type]


def _make_pool(executemany_return: str = "INSERT 0 1") -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.executemany = AsyncMock(return_value=executemany_return)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


@pytest.mark.asyncio
async def test_batch_insert_calls_executemany() -> None:
    pool = _make_pool()
    await batch_insert_anomalies(pool, [_anomaly()])
    conn = pool.acquire.return_value.__aenter__.return_value
    conn.executemany.assert_called_once()


@pytest.mark.asyncio
async def test_batch_insert_empty_list_returns_zero() -> None:
    pool = _make_pool()
    result = await batch_insert_anomalies(pool, [])
    assert result == 0
    conn = pool.acquire.return_value.__aenter__.return_value
    conn.executemany.assert_not_called()


@pytest.mark.asyncio
async def test_batch_insert_passes_correct_columns() -> None:
    pool = _make_pool()
    a = _anomaly()
    await batch_insert_anomalies(pool, [a])
    conn = pool.acquire.return_value.__aenter__.return_value
    _sql, rows = conn.executemany.call_args.args
    assert len(rows) == 1
    row = rows[0]
    assert row[3] == "payment-api"  # service
    assert row[4] == "cpu_percent"  # metric
    assert row[6] == pytest.approx(-0.25)  # score
    assert row[7] == pytest.approx(0.0)  # threshold

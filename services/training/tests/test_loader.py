"""Unit tests for the data loader — asyncpg is fully mocked."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from training.loader import discover_pairs, load_series

NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
START = NOW - timedelta(days=30)


def _make_pool(rows: list[dict]) -> MagicMock:
    """Build a mock asyncpg Pool that returns *rows* from fetch()."""
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=rows)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


@pytest.mark.asyncio
async def test_load_series_returns_dataframe() -> None:
    rows = [
        {"timestamp": NOW - timedelta(hours=i), "value": float(i)}
        for i in range(10)
    ]
    pool = _make_pool(rows)
    df = await load_series(pool, "payment-api", "cpu_percent", START, NOW)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["timestamp", "value"]
    assert len(df) == 10
    assert df["value"].dtype == float


@pytest.mark.asyncio
async def test_load_series_empty_when_no_rows() -> None:
    pool = _make_pool([])
    df = await load_series(pool, "payment-api", "cpu_percent", START, NOW)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert "timestamp" in df.columns
    assert "value" in df.columns


@pytest.mark.asyncio
async def test_discover_pairs_returns_tuples() -> None:
    rows = [
        {"service": "payment-api", "metric": "cpu_percent"},
        {"service": "auth-service", "metric": "latency_p99"},
    ]
    pool = _make_pool(rows)
    pairs = await discover_pairs(pool, since=START)
    assert len(pairs) == 2
    assert ("payment-api", "cpu_percent") in pairs
    assert ("auth-service", "latency_p99") in pairs


@pytest.mark.asyncio
async def test_discover_pairs_empty_db() -> None:
    pool = _make_pool([])
    pairs = await discover_pairs(pool, since=START)
    assert pairs == []

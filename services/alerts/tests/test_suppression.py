"""Unit tests for alert suppression — Redis is fully mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from alerts.suppression import _key, clear, is_suppressed, mark_fired


def _mock_redis(exists_return: int = 0) -> MagicMock:
    r = AsyncMock()
    r.exists = AsyncMock(return_value=exists_return)
    r.set = AsyncMock(return_value=True)
    r.delete = AsyncMock(return_value=1)
    return r


@pytest.mark.asyncio
async def test_not_suppressed_initially() -> None:
    redis = _mock_redis(exists_return=0)
    result = await is_suppressed(redis, "payment-api", "cpu_percent")
    assert result is False


@pytest.mark.asyncio
async def test_suppressed_when_key_exists() -> None:
    redis = _mock_redis(exists_return=1)
    result = await is_suppressed(redis, "payment-api", "cpu_percent")
    assert result is True


@pytest.mark.asyncio
async def test_mark_fired_calls_set_with_ttl() -> None:
    redis = _mock_redis()
    await mark_fired(redis, "payment-api", "cpu_percent", window_secs=300)
    redis.set.assert_awaited_once_with(_key("payment-api", "cpu_percent"), "1", ex=300, nx=True)


@pytest.mark.asyncio
async def test_suppression_different_series_are_independent() -> None:
    # First series is suppressed, second is not
    redis = AsyncMock()
    redis.exists = AsyncMock(side_effect=lambda k: 1 if "payment-api" in k else 0)

    assert await is_suppressed(redis, "payment-api", "cpu_percent") is True
    assert await is_suppressed(redis, "auth-service", "latency_p99") is False


@pytest.mark.asyncio
async def test_clear_deletes_key() -> None:
    redis = _mock_redis()
    await clear(redis, "payment-api", "cpu_percent")
    redis.delete.assert_awaited_once_with(_key("payment-api", "cpu_percent"))

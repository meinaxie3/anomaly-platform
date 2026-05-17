"""
Unit tests for consumer retry logic, PEL drain, and dead-letter behaviour.
All Redis and asyncpg interactions are mocked — no infrastructure needed.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ap_schemas import MetricEvent
from consumer.worker import _drain_pel, _write_with_retry


def _make_event(**kwargs) -> MetricEvent:  # type: ignore[no-untyped-def]
    defaults = dict(
        service="payment-api",
        metric="cpu_percent",
        value=55.0,
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
    )
    return MetricEvent(**(defaults | kwargs))


def _make_pool(inserted: int = 1) -> MagicMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=f"INSERT 0 {inserted}")
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    return pool


def _make_redis() -> MagicMock:
    redis = MagicMock()
    pipe = MagicMock()
    pipe.xadd = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


# ── _write_with_retry ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_succeeds_on_first_attempt() -> None:
    events = [_make_event()]
    msg_ids = [b"1-0"]
    pool = _make_pool(inserted=1)
    redis = _make_redis()

    with patch("consumer.worker.batch_insert", new=AsyncMock(return_value=1)):
        inserted, skipped = await _write_with_retry(pool, events, msg_ids, redis, "dlq")

    assert inserted == 1
    assert skipped == 0
    redis.pipeline.assert_not_called()  # no dead-lettering


@pytest.mark.asyncio
async def test_write_retries_on_transient_error_then_succeeds() -> None:
    events = [_make_event()]
    msg_ids = [b"1-0"]
    pool = _make_pool()
    redis = _make_redis()

    call_count = 0

    async def flaky_insert(*_args, **_kwargs) -> int:  # type: ignore[no-untyped-def]
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("transient pg error")
        return 1

    with (
        patch("consumer.worker.batch_insert", new=flaky_insert),
        patch("consumer.worker.asyncio.sleep", new=AsyncMock()),
    ):
        inserted, _skipped = await _write_with_retry(pool, events, msg_ids, redis, "dlq")

    assert inserted == 1
    assert call_count == 2
    redis.pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_write_dead_letters_after_all_retries_exhausted() -> None:
    events = [_make_event()]
    msg_ids = [b"1-0"]
    pool = _make_pool()
    redis = _make_redis()

    async def always_fails(*_args, **_kwargs) -> int:  # type: ignore[no-untyped-def]
        raise RuntimeError("permanent pg error")

    with (
        patch("consumer.worker.batch_insert", new=always_fails),
        patch("consumer.worker.asyncio.sleep", new=AsyncMock()),
    ):
        inserted, _skipped = await _write_with_retry(pool, events, msg_ids, redis, "dlq")

    assert inserted == 0
    # DLQ pipe was used
    pipe = redis.pipeline.return_value
    pipe.xadd.assert_called_once()
    pipe.execute.assert_called_once()


@pytest.mark.asyncio
async def test_write_dead_letters_each_message_id() -> None:
    events = [_make_event(), _make_event(value=10.0)]
    msg_ids = [b"1-0", b"2-0"]
    pool = _make_pool()
    redis = _make_redis()

    async def always_fails(*_args, **_kwargs) -> int:  # type: ignore[no-untyped-def]
        raise RuntimeError("pg down")

    with (
        patch("consumer.worker.batch_insert", new=always_fails),
        patch("consumer.worker.asyncio.sleep", new=AsyncMock()),
    ):
        await _write_with_retry(pool, events, msg_ids, redis, "dlq")

    pipe = redis.pipeline.return_value
    assert pipe.xadd.call_count == 2


# ── _drain_pel ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pel_drain_reprocesses_pending_messages() -> None:
    event = _make_event()
    raw = event.model_dump_json().encode()
    pending_message = (b"9-0", {b"data": raw})

    redis = _make_redis()
    redis.xreadgroup = AsyncMock(
        side_effect=[
            [(b"metrics:stream", [pending_message])],  # first call: 1 pending message
            [],  # second call: PEL empty
        ]
    )
    redis.xack = AsyncMock()
    pool = _make_pool()

    with patch("consumer.worker.batch_insert", new=AsyncMock(return_value=1)):
        await _drain_pel(redis, pool, "metrics:stream", "g", "c", "dlq", 500)

    redis.xack.assert_called_once_with("metrics:stream", "g", b"9-0")


@pytest.mark.asyncio
async def test_pel_drain_noop_when_pel_is_empty() -> None:
    redis = _make_redis()
    redis.xreadgroup = AsyncMock(return_value=[])
    redis.xack = AsyncMock()
    pool = _make_pool()

    await _drain_pel(redis, pool, "metrics:stream", "g", "c", "dlq", 500)

    redis.xack.assert_not_called()

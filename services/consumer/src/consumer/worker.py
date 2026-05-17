"""
Redis Streams consumer loop.

parse_message()     — pure function: raw stream entry -> MetricEvent (unit-testable)
_write_with_retry() — batch_insert with exponential-backoff retries and dead-letter fallback
_drain_pel()        — reprocess unACKed messages left from a prior crash
consume_loop()      — XREADGROUP -> write -> XACK main loop
"""

import asyncio
import time
from collections.abc import Sequence

import asyncpg
import redis.asyncio as aioredis
from ap_logging import get_logger
from ap_schemas import MetricEvent
from pydantic import ValidationError

from consumer.db import batch_insert
from consumer.metrics import events_dead_lettered, events_inserted, events_skipped, write_latency
from consumer.settings import Settings

log = get_logger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles on each attempt


def parse_message(entry: tuple[bytes | str, dict[bytes | str, bytes | str]]) -> MetricEvent | None:
    """
    Parse a single Redis stream entry into a MetricEvent.

    Returns None and logs a warning if the payload is malformed.
    """
    msg_id, fields = entry
    raw = fields.get(b"data") or fields.get("data")
    if raw is None:
        log.warning("stream_entry_missing_data_field", msg_id=msg_id)
        return None
    try:
        return MetricEvent.model_validate_json(raw)
    except ValidationError as exc:
        log.warning("stream_entry_invalid_json", msg_id=msg_id, error=str(exc))
        return None


async def _ensure_group(redis: aioredis.Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _write_with_retry(
    pool: asyncpg.Pool,
    events: list[MetricEvent],
    msg_ids: list[bytes | str],
    redis: aioredis.Redis,
    dlq_stream: str,
) -> tuple[int, int]:
    """
    Attempt batch_insert up to _MAX_RETRIES times with exponential backoff.

    On permanent failure, dead-letters the message IDs to dlq_stream so the
    PEL doesn't grow forever. Returns (inserted, skipped).
    """
    delay = _RETRY_BASE_DELAY
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            t0 = time.perf_counter()
            async with pool.acquire() as conn:
                inserted = await batch_insert(conn, events)
            elapsed = time.perf_counter() - t0

            write_latency.observe(elapsed)
            skipped = len(events) - inserted
            events_inserted.inc(inserted)
            events_skipped.inc(skipped)
            return inserted, skipped

        except Exception as exc:
            if attempt == _MAX_RETRIES:
                log.error(
                    "batch_insert_permanent_failure",
                    attempt=attempt,
                    error=str(exc),
                    msg_count=len(msg_ids),
                )
                pipe = redis.pipeline(transaction=False)
                for msg_id in msg_ids:
                    pipe.xadd(dlq_stream, {"failed_id": msg_id, "error": str(exc)})
                await pipe.execute()
                events_dead_lettered.inc(len(msg_ids))
                return 0, 0

            log.warning(
                "batch_insert_transient_failure", attempt=attempt, retry_in=delay, error=str(exc)
            )
            await asyncio.sleep(delay)
            delay *= 2

    return 0, 0  # unreachable; satisfies mypy


async def _drain_pel(
    redis: aioredis.Redis,
    pool: asyncpg.Pool,
    stream: str,
    group: str,
    name: str,
    dlq_stream: str,
    batch_size: int,
) -> None:
    """
    Reprocess messages that were read but never ACKed before a prior crash.
    Uses id="0" to read from the PEL instead of new messages.
    """
    log.info("pel_drain_start", stream=stream, group=group)
    total = 0

    while True:
        entries: Sequence = await redis.xreadgroup(group, name, {stream: "0"}, count=batch_size)
        if not entries:
            break

        _stream_key, messages = entries[0]
        if not messages:
            break

        events: list[MetricEvent] = []
        msg_ids: list[bytes | str] = []
        for msg_id, fields in messages:
            event = parse_message((msg_id, fields))
            if event is not None:
                events.append(event)
                msg_ids.append(msg_id)

        if events:
            inserted, _ = await _write_with_retry(pool, events, msg_ids, redis, dlq_stream)
            total += inserted

        if msg_ids:
            await redis.xack(stream, group, *msg_ids)

    log.info("pel_drain_complete", reprocessed=total)


async def consume_loop(
    redis: aioredis.Redis,
    pool: asyncpg.Pool,
    settings: Settings,
) -> None:
    stream = settings.stream_name
    group = settings.consumer_group
    name = settings.consumer_name
    dlq_stream = f"{stream}:dlq"

    await _ensure_group(redis, stream, group)
    log.info("consumer_started", stream=stream, group=group, name=name)

    await _drain_pel(redis, pool, stream, group, name, dlq_stream, settings.batch_size)

    while True:
        entries: Sequence = await redis.xreadgroup(
            group,
            name,
            {stream: ">"},
            count=settings.batch_size,
            block=settings.block_ms,
        )
        if not entries:
            continue

        _stream_key, messages = entries[0]
        events: list[MetricEvent] = []
        msg_ids: list[bytes | str] = []

        for msg_id, fields in messages:
            event = parse_message((msg_id, fields))
            if event is not None:
                events.append(event)
                msg_ids.append(msg_id)

        if events:
            inserted, skipped = await _write_with_retry(pool, events, msg_ids, redis, dlq_stream)
            log.info("batch_written", count=len(events), inserted=inserted, skipped=skipped)

        if msg_ids:
            await redis.xack(stream, group, *msg_ids)

        await asyncio.sleep(0)

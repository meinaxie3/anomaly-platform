"""
Redis Streams consumer loop.

parse_message()  — pure function: raw stream entry -> MetricEvent (unit-testable)
consume_loop()   — XREADGROUP -> batch_insert -> XACK cycle
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
from consumer.metrics import events_inserted, events_skipped, write_latency
from consumer.settings import Settings

log = get_logger(__name__)


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


async def consume_loop(
    redis: aioredis.Redis,
    pool: asyncpg.Pool,
    settings: Settings,
) -> None:
    stream = settings.stream_name
    group = settings.consumer_group
    name = settings.consumer_name

    await _ensure_group(redis, stream, group)
    log.info("consumer_started", stream=stream, group=group, name=name)

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
            t0 = time.perf_counter()
            async with pool.acquire() as conn:
                inserted = await batch_insert(conn, events)
            elapsed = time.perf_counter() - t0

            write_latency.observe(elapsed)
            events_inserted.inc(inserted)
            events_skipped.inc(len(events) - inserted)

            log.info(
                "batch_written",
                count=len(events),
                inserted=inserted,
                skipped=len(events) - inserted,
                elapsed_ms=round(elapsed * 1000, 1),
            )

        if msg_ids:
            await redis.xack(stream, group, *msg_ids)

        await asyncio.sleep(0)

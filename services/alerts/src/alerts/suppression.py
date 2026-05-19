"""Redis-backed alert suppression.

Uses SET ... EX ... NX (set-if-not-exists with TTL) for atomic suppression
checks. A key present in Redis means an alert for that series was already fired
within the suppression window — don't fire again.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from ap_logging import get_logger

log = get_logger(__name__)

_KEY_PREFIX = "alerts:suppression"


def _key(service: str, metric: str) -> str:
    return f"{_KEY_PREFIX}:{service}:{metric}"


async def is_suppressed(redis: aioredis.Redis, service: str, metric: str) -> bool:
    """Return True if an alert for *(service, metric)* was already fired recently."""
    exists = await redis.exists(_key(service, metric))
    return bool(exists)


async def mark_fired(
    redis: aioredis.Redis,
    service: str,
    metric: str,
    window_secs: int = 300,
) -> None:
    """Record that an alert was fired for *(service, metric)*.

    The key expires automatically after *window_secs*, re-enabling alerts.
    Uses SET NX so concurrent alert cycles don't extend the window.
    """
    await redis.set(_key(service, metric), "1", ex=window_secs, nx=True)
    log.info("alert_suppression_set", service=service, metric=metric, window_secs=window_secs)


async def clear(redis: aioredis.Redis, service: str, metric: str) -> None:
    """Manually clear the suppression key — useful for testing."""
    await redis.delete(_key(service, metric))

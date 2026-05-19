"""Alert engine entry point — polling loop."""

from __future__ import annotations

import asyncio

import asyncpg
import redis.asyncio as aioredis

from ap_logging import get_logger
from alerts.engine import run_alert_cycle
from alerts.settings import get_settings

log = get_logger(__name__)


async def _loop() -> None:
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.postgres_url, min_size=1, max_size=4)
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    log.info(
        "alert_engine_started",
        poll_interval_secs=settings.poll_interval_secs,
        grouping_window_secs=settings.grouping_window_secs,
        suppression_window_secs=settings.suppression_window_secs,
    )

    try:
        while True:
            try:
                await run_alert_cycle(pool, redis, settings)
            except Exception as exc:
                log.error("alert_cycle_error", error=str(exc))
            await asyncio.sleep(settings.poll_interval_secs)
    finally:
        await pool.close()
        await redis.aclose()


def main() -> None:
    asyncio.run(_loop())


if __name__ == "__main__":
    main()

import asyncio

import asyncpg
import redis.asyncio as aioredis
from ap_logging import configure_logging, get_logger
from prometheus_client import start_http_server

from consumer.settings import get_settings
from consumer.worker import consume_loop


async def main() -> None:
    settings = get_settings()
    configure_logging("consumer", settings.env, settings.log_level)
    log = get_logger(__name__)

    start_http_server(settings.metrics_port)
    log.info("metrics_server_started", port=settings.metrics_port)

    redis: aioredis.Redis = aioredis.from_url(settings.redis_url, decode_responses=False)
    pool: asyncpg.Pool = await asyncpg.create_pool(settings.postgres_url)

    log.info("consumer_connecting", redis=settings.redis_url, postgres=settings.postgres_url)
    try:
        await consume_loop(redis, pool, settings)
    finally:
        await redis.aclose()
        await pool.close()
        log.info("consumer_shutdown")


def main_sync() -> None:
    asyncio.run(main())

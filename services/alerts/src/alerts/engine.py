"""Alert engine — one polling cycle: fetch → group → suppress → persist."""

from __future__ import annotations

import asyncpg
import redis.asyncio as aioredis
from ap_logging import get_logger

from alerts import db, suppression
from alerts.grouper import group_into_incidents
from alerts.settings import Settings

log = get_logger(__name__)


async def run_alert_cycle(
    pool: asyncpg.Pool,
    redis: aioredis.Redis,
    settings: Settings,
) -> tuple[int, int]:
    """Execute one alert cycle.

    Returns:
        (incidents_created, incidents_suppressed)
    """
    anomalies = await db.fetch_ungrouped_anomalies(pool)
    if not anomalies:
        return 0, 0

    grouped = group_into_incidents(anomalies, settings.grouping_window_secs)
    created = 0
    suppressed = 0

    for incident, members in grouped:
        if await suppression.is_suppressed(redis, incident.service, incident.metric):
            log.info(
                "incident_suppressed",
                service=incident.service,
                metric=incident.metric,
                n_anomalies=len(members),
            )
            suppressed += 1
            continue

        member_ids = [a.anomaly_id for a in members]
        await db.persist_incident(pool, incident, member_ids)
        await suppression.mark_fired(
            redis,
            incident.service,
            incident.metric,
            window_secs=settings.suppression_window_secs,
        )
        created += 1

    log.info(
        "alert_cycle_complete",
        ungrouped_anomalies=len(anomalies),
        incidents_created=created,
        incidents_suppressed=suppressed,
    )
    return created, suppressed

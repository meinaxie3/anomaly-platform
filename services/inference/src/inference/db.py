"""Anomaly persistence — writes AnomalyRecord rows to TimescaleDB."""

from __future__ import annotations

import asyncpg
from ap_logging import get_logger
from ap_schemas import AnomalyRecord

log = get_logger(__name__)

_INSERT = """
    INSERT INTO anomalies (
        anomaly_id, event_id, timestamp,
        service, metric, value,
        score, threshold, model_id,
        status
    ) VALUES (
        $1, $2, $3,
        $4, $5, $6,
        $7, $8, $9,
        'open'
    )
    ON CONFLICT (event_id) DO NOTHING
"""


async def batch_insert_anomalies(
    pool: asyncpg.Pool,
    anomalies: list[AnomalyRecord],
) -> int:
    """Insert anomaly records, ignoring duplicates (idempotent on event_id).

    Returns the number of rows actually inserted.
    """
    if not anomalies:
        return 0

    rows = [
        (
            a.anomaly_id,
            a.event_id,
            a.timestamp,
            a.service,
            a.metric,
            a.value,
            a.score,
            a.threshold,
            a.model_id,
        )
        for a in anomalies
    ]

    async with pool.acquire() as conn:
        result = await conn.executemany(_INSERT, rows)

    # asyncpg executemany returns a string like "INSERT 0 N"
    try:
        inserted = int(result.split()[-1]) if result else 0
    except (AttributeError, ValueError, IndexError):
        inserted = len(anomalies)  # fallback — assume all inserted

    log.info("anomalies_persisted", inserted=inserted, total=len(anomalies))
    return inserted

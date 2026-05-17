"""TimescaleDB data loader for the training pipeline."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

import asyncpg

from ap_logging import get_logger

log = get_logger(__name__)

_SERIES_QUERY = """
    SELECT timestamp, value
    FROM   metrics
    WHERE  service   = $1
      AND  metric    = $2
      AND  timestamp >= $3
      AND  timestamp <  $4
    ORDER  BY timestamp ASC
"""

_PAIRS_QUERY = """
    SELECT DISTINCT service, metric
    FROM   metrics
    WHERE  timestamp >= $1
    ORDER  BY service, metric
"""


async def load_series(
    pool: asyncpg.Pool,
    service: str,
    metric: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    """Return a DataFrame with columns [timestamp, value] for the given window.

    Rows are ordered by timestamp ascending.  Returns an empty DataFrame (same
    schema) when no rows exist — callers must check ``len(df) > 0`` before use.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SERIES_QUERY, service, metric, start, end)

    if not rows:
        log.warning(
            "no_data_found",
            service=service,
            metric=metric,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        return pd.DataFrame(columns=["timestamp", "value"])

    df = pd.DataFrame(rows, columns=["timestamp", "value"])
    df["value"] = df["value"].astype(float)
    log.info(
        "series_loaded",
        service=service,
        metric=metric,
        n_rows=len(df),
        start=start.isoformat(),
        end=end.isoformat(),
    )
    return df


async def discover_pairs(
    pool: asyncpg.Pool,
    since: datetime,
) -> list[tuple[str, str]]:
    """Return all unique (service, metric) pairs seen since *since*.

    Used by the job to know which models to train without hard-coding the list.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(_PAIRS_QUERY, since)
    pairs = [(row["service"], row["metric"]) for row in rows]
    log.info("pairs_discovered", count=len(pairs), since=since.isoformat())
    return pairs

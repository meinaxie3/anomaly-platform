"""
asyncpg helpers for writing MetricEvents to TimescaleDB.

batch_insert() — single unnested upsert; idempotent via ON CONFLICT DO NOTHING.
"""

import json
from datetime import datetime
from uuid import UUID

import asyncpg
from ap_schemas import MetricEvent

_INSERT_SQL = """
INSERT INTO metrics (timestamp, event_id, service, metric, value, labels)
SELECT * FROM UNNEST(
    $1::timestamptz[],
    $2::uuid[],
    $3::text[],
    $4::text[],
    $5::float8[],
    $6::jsonb[]
)
ON CONFLICT (timestamp, event_id) DO NOTHING
"""


def _to_columns(
    events: list[MetricEvent],
) -> tuple[list[datetime], list[UUID], list[str], list[str], list[float], list[str]]:
    """Split a list of events into column-oriented lists for asyncpg UNNEST."""
    return (
        [e.timestamp for e in events],
        [e.event_id for e in events],
        [e.service for e in events],
        [e.metric for e in events],
        [e.value for e in events],
        [json.dumps(e.labels) for e in events],
    )


async def batch_insert(conn: asyncpg.Connection, events: list[MetricEvent]) -> int:
    """Insert events and return the count actually written (duplicates skipped)."""
    if not events:
        return 0
    cols = _to_columns(events)
    result: str = await conn.execute(_INSERT_SQL, *cols)
    return int(result.split()[-1])

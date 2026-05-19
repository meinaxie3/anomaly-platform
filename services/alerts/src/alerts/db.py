"""Alert engine DB operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from ap_logging import get_logger
from ap_schemas import AnomalyRecord, IncidentRecord

log = get_logger(__name__)

_FETCH_UNGROUPED = """
    SELECT anomaly_id, event_id, timestamp,
           service, metric, value,
           score, threshold, model_id, status
    FROM   anomalies
    WHERE  incident_id IS NULL
    ORDER  BY service, metric, timestamp ASC
"""

_INSERT_INCIDENT = """
    INSERT INTO incidents (incident_id, service, metric, status, started_at)
    VALUES ($1, $2, $3, 'open', $4)
"""

_LINK_ANOMALIES = """
    UPDATE anomalies
    SET    incident_id = $1
    WHERE  anomaly_id = ANY($2::uuid[])
"""

_RESOLVE_INCIDENT = """
    UPDATE incidents
    SET    status = 'resolved', resolved_at = $2
    WHERE  incident_id = $1
"""


async def fetch_ungrouped_anomalies(pool: asyncpg.Pool) -> list[AnomalyRecord]:
    """Return all anomaly rows that have not yet been assigned to an incident."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_FETCH_UNGROUPED)
    return [_row_to_anomaly(r) for r in rows]


async def persist_incident(
    pool: asyncpg.Pool,
    incident: IncidentRecord,
    member_anomaly_ids: list[UUID],
) -> None:
    """Atomically insert the incident and link its member anomalies."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                _INSERT_INCIDENT,
                incident.incident_id,
                incident.service,
                incident.metric,
                incident.started_at,
            )
            await conn.execute(
                _LINK_ANOMALIES,
                incident.incident_id,
                member_anomaly_ids,
            )
    log.info(
        "incident_persisted",
        incident_id=str(incident.incident_id),
        service=incident.service,
        metric=incident.metric,
        n_anomalies=len(member_anomaly_ids),
    )


async def resolve_incident(pool: asyncpg.Pool, incident_id: UUID) -> None:
    """Soft-close an incident by setting resolved_at and status='resolved'."""
    now = datetime.now(tz=UTC)
    async with pool.acquire() as conn:
        await conn.execute(_RESOLVE_INCIDENT, incident_id, now)
    log.info("incident_resolved", incident_id=str(incident_id))


def _row_to_anomaly(row: asyncpg.Record) -> AnomalyRecord:
    return AnomalyRecord(
        anomaly_id=row["anomaly_id"],
        event_id=row["event_id"],
        service=row["service"],
        metric=row["metric"],
        value=row["value"],
        score=row["score"],
        threshold=row["threshold"],
        model_id=str(row["model_id"]),
        timestamp=row["timestamp"],
        resolved=row["status"] != "open",
    )

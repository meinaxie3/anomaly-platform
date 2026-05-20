"""Dashboard API -- read-only DB queries.

All functions accept an asyncpg.Pool and return typed Python objects.
No writes happen here; the dashboard is a pure read layer.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal

import asyncpg

from ap_logging import get_logger

from dashboard_api.schemas import (
    AnomalyMarker,
    IncidentSummary,
    MetricPoint,
    MetricSeries,
    ModelSummary,
    ServiceSummary,
)

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# /services
# ---------------------------------------------------------------------------

_SERVICES_QUERY = """
    SELECT
        svc.service,
        COALESCE(inc.open_incidents, 0)  AS open_incidents,
        anom.last_anomaly_at
    FROM (
        SELECT DISTINCT service FROM metrics
    ) svc
    LEFT JOIN (
        SELECT service, COUNT(*) AS open_incidents
        FROM   incidents
        WHERE  status = 'open'
        GROUP  BY service
    ) inc ON inc.service = svc.service
    LEFT JOIN (
        SELECT service, MAX(timestamp) AS last_anomaly_at
        FROM   anomalies
        GROUP  BY service
    ) anom ON anom.service = svc.service
    ORDER BY svc.service
"""


def _health(open_incidents: int) -> Literal["healthy", "degraded", "critical"]:
    if open_incidents == 0:
        return "healthy"
    if open_incidents <= 2:
        return "degraded"
    return "critical"


async def fetch_services(pool: asyncpg.Pool) -> list[ServiceSummary]:
    """Return one summary row per known service."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_SERVICES_QUERY)
    return [
        ServiceSummary(
            service=r["service"],
            open_incidents=r["open_incidents"],
            last_anomaly_at=r["last_anomaly_at"],
            health=_health(r["open_incidents"]),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# /metrics/{service}/{metric}
# ---------------------------------------------------------------------------

# For windows > aggregate_threshold_hours: read the 1-min continuous aggregate.
_AGG_SERIES_QUERY = """
    SELECT
        bucket,
        avg_value,
        min_value,
        max_value,
        sample_count
    FROM metrics_1min
    WHERE service     = $1
      AND metric      = $2
      AND bucket     >= $3
      AND bucket      < $4
    ORDER BY bucket ASC
    LIMIT $5
"""

# For short windows: read raw metrics bucketed by the finest useful resolution.
_RAW_SERIES_QUERY = """
    SELECT
        time_bucket('10 seconds', timestamp) AS bucket,
        AVG(value)                           AS avg_value,
        MIN(value)                           AS min_value,
        MAX(value)                           AS max_value,
        COUNT(*)                             AS sample_count
    FROM metrics
    WHERE service   = $1
      AND metric    = $2
      AND timestamp >= $3
      AND timestamp  < $4
    GROUP BY bucket
    ORDER BY bucket ASC
    LIMIT $5
"""

_ANOMALY_MARKERS_QUERY = """
    SELECT timestamp, value, score
    FROM   anomalies
    WHERE  service   = $1
      AND  metric    = $2
      AND  timestamp >= $3
      AND  timestamp  < $4
    ORDER  BY timestamp ASC
"""


async def fetch_metric_series(
    pool: asyncpg.Pool,
    service: str,
    metric: str,
    from_dt: datetime,
    to_dt: datetime,
    *,
    aggregate_threshold_hours: float = 2.0,
    max_points: int = 500,
) -> MetricSeries:
    """Return aggregated metric points + anomaly markers for one series."""
    window_hours = (to_dt - from_dt).total_seconds() / 3600
    use_agg = window_hours > aggregate_threshold_hours

    series_query = _AGG_SERIES_QUERY if use_agg else _RAW_SERIES_QUERY

    # Use two separate connections: asyncpg does not allow concurrent queries
    # on a single connection, so asyncio.gather needs one conn per coroutine.
    async def _fetch_points() -> list:
        async with pool.acquire() as conn:
            return await conn.fetch(series_query, service, metric, from_dt, to_dt, max_points)

    async def _fetch_anomalies() -> list:
        async with pool.acquire() as conn:
            return await conn.fetch(_ANOMALY_MARKERS_QUERY, service, metric, from_dt, to_dt)

    point_rows, anomaly_rows = await asyncio.gather(_fetch_points(), _fetch_anomalies())

    log.debug(
        "metric_series_fetched",
        service=service,
        metric=metric,
        points=len(point_rows),
        anomalies=len(anomaly_rows),
        source="agg" if use_agg else "raw",
    )

    points = [
        MetricPoint(
            bucket=r["bucket"],
            avg_value=float(r["avg_value"]),
            min_value=float(r["min_value"]),
            max_value=float(r["max_value"]),
            sample_count=int(r["sample_count"]),
        )
        for r in point_rows
    ]
    anomalies = [
        AnomalyMarker(
            timestamp=r["timestamp"],
            value=float(r["value"]),
            score=float(r["score"]),
        )
        for r in anomaly_rows
    ]
    return MetricSeries(service=service, metric=metric, points=points, anomalies=anomalies)


# ---------------------------------------------------------------------------
# /incidents
# ---------------------------------------------------------------------------

_INCIDENTS_QUERY = """
    SELECT
        i.incident_id,
        i.service,
        i.metric,
        i.status,
        i.started_at,
        i.resolved_at,
        COUNT(a.anomaly_id) AS anomaly_count
    FROM  incidents i
    LEFT  JOIN anomalies a ON a.incident_id = i.incident_id
    WHERE ($1::text IS NULL OR i.status = $1)
    GROUP BY i.incident_id
    ORDER BY i.started_at DESC
    LIMIT  $2
    OFFSET $3
"""


async def fetch_incidents(
    pool: asyncpg.Pool,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[IncidentSummary]:
    """Return paginated incidents, optionally filtered by status."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_INCIDENTS_QUERY, status, limit, offset)
    return [
        IncidentSummary(
            incident_id=r["incident_id"],
            service=r["service"],
            metric=r["metric"],
            status=r["status"],
            started_at=r["started_at"],
            resolved_at=r["resolved_at"],
            anomaly_count=int(r["anomaly_count"]),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# /models
# ---------------------------------------------------------------------------

_MODELS_QUERY = """
    SELECT
        model_id,
        service,
        metric,
        algorithm,
        trained_at,
        n_samples,
        fit_seconds,
        eval_f1,
        is_current,
        window_start,
        window_end
    FROM model_registry
    WHERE ($1::text IS NULL OR service = $1)
      AND ($2::bool IS NULL OR is_current = $2)
    ORDER BY trained_at DESC
    LIMIT 200
"""


async def fetch_models(
    pool: asyncpg.Pool,
    service: str | None = None,
    is_current: bool | None = None,
) -> list[ModelSummary]:
    """Return model registry rows, optionally filtered."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(_MODELS_QUERY, service, is_current)
    return [
        ModelSummary(
            model_id=str(r["model_id"]),
            service=r["service"],
            metric=r["metric"],
            algorithm=r["algorithm"],
            trained_at=r["trained_at"],
            n_samples=r["n_samples"],
            fit_seconds=float(r["fit_seconds"]),
            eval_f1=float(r["eval_f1"]),
            is_current=r["is_current"],
            window_start=r["window_start"],
            window_end=r["window_end"],
        )
        for r in rows
    ]

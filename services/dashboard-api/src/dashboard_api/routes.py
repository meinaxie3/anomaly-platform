"""Dashboard API routes -- all read-only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request

from ap_logging import get_logger

from dashboard_api import db
from dashboard_api.schemas import (
    IncidentSummary,
    MetricSeries,
    ModelSummary,
    ServiceSummary,
)

log = get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /services
# ---------------------------------------------------------------------------


@router.get("/services", response_model=list[ServiceSummary])
async def list_services(request: Request) -> list[ServiceSummary]:
    """Return one summary row per service: health status, open incident count,
    and time of last anomaly."""
    pool = request.app.state.pool
    return await db.fetch_services(pool)


# ---------------------------------------------------------------------------
# /metrics/{service}/{metric}
# ---------------------------------------------------------------------------


def _parse_dt(raw: str | None, fallback: datetime) -> datetime:
    """Parse an ISO-8601 string (with or without timezone) into an aware datetime.

    Accepts the ``from`` / ``to`` params as plain strings so that the ``+``
    in ``+00:00`` offsets is never mis-interpreted as a URL space character
    (which happens when FastAPI tries to coerce the raw query string via
    Pydantic's datetime validator before URL-decoding is complete).
    """
    if raw is None:
        return fallback
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {raw!r}")
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@router.get("/metrics/{service}/{metric}", response_model=MetricSeries)
async def get_metric_series(
    service: str,
    metric: str,
    request: Request,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
) -> MetricSeries:
    """Return aggregated metric points + anomaly markers for one (service, metric) pair.

    - Default window: last 3 hours.
    - Windows > 2 h read ``metrics_1min`` (Timescale continuous aggregate).
    - Windows <= 2 h read raw ``metrics`` bucketed at 10-second resolution.
    - The ``from`` param is capped at 30 days ago to prevent full-table scans.
    """
    settings = request.app.state.settings
    pool = request.app.state.pool
    now = datetime.now(tz=UTC)

    default_from = now - timedelta(hours=settings.default_window_hours)
    from_dt = _parse_dt(from_, default_from)
    to_dt = _parse_dt(to, now)

    if to_dt > now + timedelta(minutes=1):
        raise HTTPException(status_code=400, detail="`to` cannot be in the future")

    earliest_allowed = now - timedelta(days=settings.max_window_days)
    if from_dt < earliest_allowed:
        raise HTTPException(
            status_code=400,
            detail=f"`from` cannot be more than {settings.max_window_days} days ago",
        )
    if from_dt >= to_dt:
        raise HTTPException(status_code=400, detail="`from` must be before `to`")

    return await db.fetch_metric_series(
        pool,
        service,
        metric,
        from_dt,
        to_dt,
        aggregate_threshold_hours=settings.aggregate_threshold_hours,
        max_points=settings.max_raw_points,
    )


# ---------------------------------------------------------------------------
# /incidents
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"open", "resolved", "suppressed"}


@router.get("/incidents", response_model=list[IncidentSummary])
async def list_incidents(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[IncidentSummary]:
    """Return paginated incidents.  Filter by ``?status=open`` or ``resolved``."""
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(_VALID_STATUSES)}",
        )
    pool = request.app.state.pool
    return await db.fetch_incidents(pool, status=status, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# /models
# ---------------------------------------------------------------------------


@router.get("/models", response_model=list[ModelSummary])
async def list_models(
    request: Request,
    service: str | None = Query(default=None),
    current_only: bool = Query(default=False),
) -> list[ModelSummary]:
    """Return model registry entries.  Filter by service and/or current-only."""
    pool = request.app.state.pool
    return await db.fetch_models(
        pool,
        service=service,
        is_current=True if current_only else None,
    )

"""Response schemas for the dashboard API.

These are dashboard-specific shapes and live here rather than in ap_schemas
(which carries only cross-service event/anomaly/incident primitives).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ServiceSummary(BaseModel):
    """Per-service health roll-up shown on the Overview page."""

    service: str
    open_incidents: int
    last_anomaly_at: datetime | None
    # Derived from open_incidents: 0=healthy, 1-2=degraded, 3+=critical
    health: Literal["healthy", "degraded", "critical"]


class MetricPoint(BaseModel):
    """One time-bucket of aggregated metric data."""

    bucket: datetime
    avg_value: float
    min_value: float
    max_value: float
    sample_count: int


class AnomalyMarker(BaseModel):
    """A single anomaly event overlaid on the metric chart."""

    timestamp: datetime
    value: float
    score: float = Field(description="Raw decision_function output — negative means anomaly")


class MetricSeries(BaseModel):
    """Full payload for one (service, metric) chart."""

    service: str
    metric: str
    points: list[MetricPoint]
    anomalies: list[AnomalyMarker]


class IncidentSummary(BaseModel):
    """Incident row for the incident feed."""

    incident_id: UUID
    service: str
    metric: str
    status: str
    started_at: datetime
    resolved_at: datetime | None
    anomaly_count: int


class ModelSummary(BaseModel):
    """One row in the Models view."""

    model_id: str
    service: str
    metric: str
    algorithm: str
    trained_at: datetime
    n_samples: int
    fit_seconds: float
    eval_precision: float = Field(description="-1.0 means not evaluated yet")
    eval_recall: float = Field(description="-1.0 means not evaluated yet")
    eval_f1: float = Field(description="-1.0 means not evaluated yet")
    is_current: bool
    window_start: datetime
    window_end: datetime

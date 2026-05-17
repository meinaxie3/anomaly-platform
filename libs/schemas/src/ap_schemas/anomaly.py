from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class IncidentStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AnomalyRecord(BaseModel):
    """A scored metric event that crossed the anomaly threshold."""

    anomaly_id: UUID = Field(default_factory=uuid4)
    event_id: UUID
    service: str
    metric: str
    value: float
    score: float = Field(description="Raw anomaly score from the model")
    threshold: float = Field(description="Threshold in use at scoring time")
    model_id: str = Field(description="Version of the model that produced this score")
    timestamp: datetime
    resolved: bool = False


class IncidentRecord(BaseModel):
    """A deduplicated, grouped incident surfaced by the alert engine."""

    incident_id: UUID = Field(default_factory=uuid4)
    service: str
    metric: str
    status: IncidentStatus = IncidentStatus.OPEN
    started_at: datetime
    resolved_at: datetime | None = None
    anomaly_ids: list[UUID] = Field(default_factory=list)

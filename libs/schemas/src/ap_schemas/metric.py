from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MetricType(StrEnum):
    CPU_PERCENT = "cpu_percent"
    MEMORY_PERCENT = "memory_percent"
    REQUEST_RATE = "request_rate"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    ERROR_RATE = "error_rate"


class MetricEvent(BaseModel):
    """A single metric observation emitted by a service."""

    event_id: UUID = Field(default_factory=uuid4, description="Idempotency key")
    service: str = Field(description="Logical service name, e.g. 'payment-api'")
    metric: str = Field(description="Metric name, e.g. 'cpu_percent'")
    value: float
    timestamp: datetime
    labels: dict[str, str] = Field(default_factory=dict)

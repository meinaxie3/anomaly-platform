"""
Load anomaly specs from a YAML schedule file.

YAML format:
    anomalies:
      - service: payment-api
        metric: cpu_percent
        type: spike
        start_offset_hours: 24.0
        duration_minutes: 30.0      # use duration_minutes OR duration_hours
        magnitude: 5.0
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, model_validator

from load_gen.anomaly import AnomalySpec, AnomalyType


class _AnomalyEntry(BaseModel):
    service: str
    metric: str
    type: AnomalyType
    start_offset_hours: float
    duration_minutes: float | None = None
    duration_hours: float | None = None
    magnitude: float

    @model_validator(mode="after")
    def _require_duration(self) -> "_AnomalyEntry":
        if self.duration_minutes is None and self.duration_hours is None:
            raise ValueError(
                f"Anomaly for {self.service}/{self.metric} must set "
                "duration_minutes or duration_hours"
            )
        return self

    def to_spec(self, simulation_start: datetime) -> AnomalySpec:
        if self.duration_minutes is not None:
            duration = timedelta(minutes=self.duration_minutes)
        else:
            duration = timedelta(hours=self.duration_hours)  # type: ignore[arg-type]
        return AnomalySpec(
            service=self.service,
            metric=self.metric,
            anomaly_type=self.type,
            start=simulation_start + timedelta(hours=self.start_offset_hours),
            duration=duration,
            magnitude=self.magnitude,
        )


def load_anomaly_specs(path: Path, simulation_start: datetime) -> list[AnomalySpec]:
    """Parse a YAML anomaly schedule and resolve offsets to absolute datetimes."""
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [_AnomalyEntry.model_validate(e) for e in raw.get("anomalies", [])]
    return [e.to_spec(simulation_start) for e in entries]

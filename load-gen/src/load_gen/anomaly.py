"""
Anomaly injection model.

AnomalySpec describes a time window + perturbation for one service/metric.
apply_anomaly() is a pure function: given a normal value and a timestamp,
it returns the (possibly perturbed) value and whether the point is anomalous.

Magnitude semantics by type:
  SPIKE         — value multiplier       (5.0 -> 5x the baseline)
  DIP           — reduction fraction     (0.8 → value drops to 20% of baseline)
  LEVEL_SHIFT   — absolute addend        (+200 → always add 200 to the value)
  GRADUAL_DRIFT — total drift at window end (linear ramp from 0 → magnitude)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class AnomalyType(StrEnum):
    SPIKE = "spike"
    DIP = "dip"
    LEVEL_SHIFT = "level_shift"
    GRADUAL_DRIFT = "gradual_drift"


@dataclass(frozen=True)
class AnomalySpec:
    service: str
    metric: str
    anomaly_type: AnomalyType
    start: datetime
    duration: timedelta
    magnitude: float

    @property
    def end(self) -> datetime:
        return self.start + self.duration


def apply_anomaly(
    value: float,
    ts: datetime,
    spec: AnomalySpec,
) -> tuple[float, bool]:
    """Return (perturbed_value, is_anomalous). Pure — no side effects."""
    if not (spec.start <= ts < spec.end):
        return value, False

    match spec.anomaly_type:
        case AnomalyType.SPIKE:
            return round(value * spec.magnitude, 4), True

        case AnomalyType.DIP:
            return round(value * (1.0 - spec.magnitude), 4), True

        case AnomalyType.LEVEL_SHIFT:
            return round(value + spec.magnitude, 4), True

        case AnomalyType.GRADUAL_DRIFT:
            total_secs = spec.duration.total_seconds()
            progress = (ts - spec.start).total_seconds() / total_secs if total_secs > 0 else 1.0
            return round(value + spec.magnitude * progress, 4), True

    return value, False  # unreachable; satisfies mypy

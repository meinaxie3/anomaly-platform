"""
Synthetic time-series signal model.

Each metric is modelled as:

    value = base
          + base * daily_amp  * daily_seasonality(t)    # ±daily swing
          + base * weekly_amp * weekly_seasonality(t)   # ±weekly swing
          + N(0, noise_std)                             # gaussian noise

clamped to [min_val, max_val].
"""

import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np

# Weekday seasonality weights (Mon=0 … Sun=6).
# Positive → more activity than average; negative → less.
_WEEKLY_WEIGHTS: tuple[float, ...] = (0.5, 0.7, 0.8, 0.7, 0.5, -0.5, -0.8)


@dataclass(frozen=True)
class SignalConfig:
    base: float
    daily_amp: float = 0.30  # fraction of base for daily swing
    weekly_amp: float = 0.15  # fraction of base for weekly swing
    noise_std: float = 1.0  # absolute gaussian noise std dev
    min_val: float = 0.0
    max_val: float | None = None


def daily_seasonality(ts: datetime) -> float:
    """Return [-1, 1]. Peak at 14:00 (2 pm), trough at 02:00 (2 am)."""
    hour_frac = ts.hour + ts.minute / 60.0
    # sin(2π*(hour-8)/24): +1 at hour=14, -1 at hour=2
    return math.sin(2 * math.pi * (hour_frac - 8.0) / 24.0)


def weekly_seasonality(ts: datetime) -> float:
    """Return [-1, 1]. Higher on weekdays, lower on weekends."""
    return _WEEKLY_WEIGHTS[ts.weekday()]


def sample(config: SignalConfig, ts: datetime, rng: np.random.Generator) -> float:
    """Draw one metric observation at timestamp ts using the supplied RNG."""
    value = (
        config.base
        + config.base * config.daily_amp * daily_seasonality(ts)
        + config.base * config.weekly_amp * weekly_seasonality(ts)
        + float(rng.normal(0.0, config.noise_std))
    )
    value = max(value, config.min_val)
    if config.max_val is not None:
        value = min(value, config.max_val)
    return round(value, 4)

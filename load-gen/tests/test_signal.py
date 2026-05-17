"""Tests for signal.py — seasonality math and sample() bounds/determinism."""

from datetime import UTC, datetime

import numpy as np
import pytest
from load_gen.signal import SignalConfig, daily_seasonality, sample, weekly_seasonality

# ── Helpers ──────────────────────────────────────────────────────────────────

_UTC = UTC


def _ts(hour: int, day: int = 7) -> datetime:
    """2025-01-<day> at <hour>:00 UTC. Day 6=Mon, 7=Tue … 12=Sun."""
    return datetime(2025, 1, day, hour, 0, 0, tzinfo=_UTC)


# ── daily_seasonality ─────────────────────────────────────────────────────────


def test_daily_peak_at_2pm() -> None:
    assert daily_seasonality(_ts(14)) == pytest.approx(1.0, abs=1e-9)


def test_daily_trough_at_2am() -> None:
    assert daily_seasonality(_ts(2)) == pytest.approx(-1.0, abs=1e-9)


def test_daily_seasonality_in_range() -> None:
    for hour in range(24):
        val = daily_seasonality(_ts(hour))
        assert -1.0 <= val <= 1.0, f"hour={hour} out of range: {val}"


def test_daily_positive_during_business_hours() -> None:
    # 9 am - 7 pm should be positive (above-average load)
    for hour in range(9, 19):
        assert daily_seasonality(_ts(hour)) > 0, f"expected positive at hour {hour}"


# ── weekly_seasonality ────────────────────────────────────────────────────────


def test_weekly_positive_on_weekdays() -> None:
    # 2025-01-06 Mon … 2025-01-10 Fri
    for day in range(6, 11):
        ts = datetime(2025, 1, day, 12, tzinfo=_UTC)
        assert weekly_seasonality(ts) > 0, f"day={day} should be positive"


def test_weekly_negative_on_weekends() -> None:
    saturday = datetime(2025, 1, 11, 12, tzinfo=_UTC)
    sunday = datetime(2025, 1, 12, 12, tzinfo=_UTC)
    assert weekly_seasonality(saturday) < 0
    assert weekly_seasonality(sunday) < 0


def test_weekly_weekday_higher_than_weekend() -> None:
    tuesday = datetime(2025, 1, 7, 12, tzinfo=_UTC)
    saturday = datetime(2025, 1, 11, 12, tzinfo=_UTC)
    assert weekly_seasonality(tuesday) > weekly_seasonality(saturday)


# ── sample() ─────────────────────────────────────────────────────────────────


def test_sample_deterministic() -> None:
    config = SignalConfig(base=50, daily_amp=0.3, weekly_amp=0.15, noise_std=5)
    ts = _ts(12)
    v1 = sample(config, ts, np.random.default_rng(42))
    v2 = sample(config, ts, np.random.default_rng(42))
    assert v1 == v2


def test_sample_respects_min_val() -> None:
    # Huge noise but clamped to 0
    config = SignalConfig(base=5, daily_amp=0, weekly_amp=0, noise_std=1000, min_val=0.0)
    rng = np.random.default_rng(0)
    for _ in range(500):
        assert sample(config, _ts(3), rng) >= 0.0


def test_sample_respects_max_val() -> None:
    config = SignalConfig(base=50, daily_amp=0, weekly_amp=0, noise_std=1000, max_val=100.0)
    rng = np.random.default_rng(0)
    for _ in range(500):
        assert sample(config, _ts(14), rng) <= 100.0


def test_sample_midday_higher_than_midnight() -> None:
    # Without noise the signal is deterministic; use zero noise
    config = SignalConfig(base=50, daily_amp=0.5, weekly_amp=0, noise_std=0)
    rng = np.random.default_rng(0)
    midday = sample(config, _ts(14), rng)
    midnight = sample(config, _ts(2), rng)
    assert midday > midnight


def test_sample_weekday_higher_than_weekend() -> None:
    config = SignalConfig(base=100, daily_amp=0, weekly_amp=0.3, noise_std=0)
    rng = np.random.default_rng(0)
    tuesday = sample(config, datetime(2025, 1, 7, 12, tzinfo=_UTC), rng)
    saturday = sample(config, datetime(2025, 1, 11, 12, tzinfo=_UTC), rng)
    assert tuesday > saturday

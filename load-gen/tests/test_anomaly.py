"""Tests for anomaly.py — all four anomaly types + boundary conditions."""

from datetime import UTC, datetime, timedelta

import pytest
from load_gen.anomaly import AnomalySpec, AnomalyType, apply_anomaly

_UTC = UTC
_START = datetime(2025, 1, 7, 12, 0, 0, tzinfo=_UTC)
_DURATION = timedelta(minutes=30)
_END = _START + _DURATION
_MID = _START + timedelta(minutes=15)


def _spec(anomaly_type: AnomalyType, magnitude: float) -> AnomalySpec:
    return AnomalySpec(
        service="payment-api",
        metric="cpu_percent",
        anomaly_type=anomaly_type,
        start=_START,
        duration=_DURATION,
        magnitude=magnitude,
    )


# ── SPIKE ─────────────────────────────────────────────────────────────────────


def test_spike_multiplies_value() -> None:
    value, flag = apply_anomaly(40.0, _MID, _spec(AnomalyType.SPIKE, 5.0))
    assert value == pytest.approx(200.0, rel=1e-3)
    assert flag is True


def test_spike_at_window_start() -> None:
    value, flag = apply_anomaly(40.0, _START, _spec(AnomalyType.SPIKE, 3.0))
    assert value == pytest.approx(120.0, rel=1e-3)
    assert flag is True


# ── DIP ───────────────────────────────────────────────────────────────────────


def test_dip_reduces_to_fraction() -> None:
    # magnitude=0.8 → keep 20% of value
    value, flag = apply_anomaly(100.0, _MID, _spec(AnomalyType.DIP, 0.8))
    assert value == pytest.approx(20.0, rel=1e-3)
    assert flag is True


def test_dip_magnitude_zero_leaves_value_unchanged() -> None:
    value, flag = apply_anomaly(50.0, _MID, _spec(AnomalyType.DIP, 0.0))
    assert value == pytest.approx(50.0)
    assert flag is True


# ── LEVEL_SHIFT ───────────────────────────────────────────────────────────────


def test_level_shift_adds_constant() -> None:
    value, flag = apply_anomaly(50.0, _MID, _spec(AnomalyType.LEVEL_SHIFT, 30.0))
    assert value == pytest.approx(80.0, rel=1e-3)
    assert flag is True


def test_level_shift_same_at_start_and_mid() -> None:
    spec = _spec(AnomalyType.LEVEL_SHIFT, 25.0)
    v_start, _ = apply_anomaly(50.0, _START, spec)
    v_mid, _ = apply_anomaly(50.0, _MID, spec)
    assert v_start == v_mid  # constant addend — no ramp


# ── GRADUAL_DRIFT ─────────────────────────────────────────────────────────────


def test_gradual_drift_zero_at_window_start() -> None:
    value, flag = apply_anomaly(50.0, _START, _spec(AnomalyType.GRADUAL_DRIFT, 20.0))
    assert value == pytest.approx(50.0, abs=0.01)
    assert flag is True


def test_gradual_drift_half_at_midpoint() -> None:
    value, flag = apply_anomaly(50.0, _MID, _spec(AnomalyType.GRADUAL_DRIFT, 20.0))
    assert value == pytest.approx(60.0, rel=1e-3)
    assert flag is True


def test_gradual_drift_full_just_before_end() -> None:
    almost_end = _END - timedelta(seconds=1)
    value, _flag = apply_anomaly(50.0, almost_end, _spec(AnomalyType.GRADUAL_DRIFT, 20.0))
    assert value > 69.0  # close to 70 but not quite


# ── Boundary conditions ───────────────────────────────────────────────────────


def test_not_anomalous_one_second_before_window() -> None:
    before = _START - timedelta(seconds=1)
    value, flag = apply_anomaly(40.0, before, _spec(AnomalyType.SPIKE, 5.0))
    assert value == pytest.approx(40.0)
    assert flag is False


def test_not_anomalous_at_window_end() -> None:
    # end is exclusive
    value, flag = apply_anomaly(40.0, _END, _spec(AnomalyType.SPIKE, 5.0))
    assert value == pytest.approx(40.0)
    assert flag is False


def test_not_anomalous_after_window() -> None:
    after = _END + timedelta(minutes=5)
    value, flag = apply_anomaly(40.0, after, _spec(AnomalyType.DIP, 0.9))
    assert value == pytest.approx(40.0)
    assert flag is False


# ── AnomalySpec helpers ───────────────────────────────────────────────────────


def test_spec_end_property() -> None:
    spec = _spec(AnomalyType.SPIKE, 1.0)
    assert spec.end == _END


def test_spec_is_frozen() -> None:
    spec = _spec(AnomalyType.SPIKE, 1.0)
    with pytest.raises((AttributeError, TypeError)):
        spec.magnitude = 99.0  # type: ignore[misc]

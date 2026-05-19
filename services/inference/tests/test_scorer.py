"""Unit tests for the scorer — uses a real fitted IsolationForest."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import IsolationForest

from ap_schemas import MetricEvent
from inference.scorer import is_anomaly, score_event


def _fitted_model(seed: int = 42) -> IsolationForest:
    """Fit on tight normal distribution so extreme values are clearly anomalous."""
    rng = np.random.default_rng(seed)
    X = rng.normal(loc=50.0, scale=2.0, size=(500, 1))
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=seed)
    model.fit(X)
    return model


def _event(value: float) -> MetricEvent:
    return MetricEvent(
        service="payment-api",
        metric="cpu_percent",
        value=value,
        timestamp=datetime.now(tz=UTC),
    )


# ── score_event ───────────────────────────────────────────────────────────────


def test_score_normal_value_is_positive() -> None:
    model = _fitted_model()
    score = score_event(model, _event(50.0))  # right at the mean — normal
    assert score > 0.0


def test_score_extreme_spike_is_negative() -> None:
    model = _fitted_model()
    score = score_event(model, _event(500.0))  # 10× spike — anomaly
    assert score < 0.0


def test_score_returns_float() -> None:
    score = score_event(_fitted_model(), _event(50.0))
    assert isinstance(score, float)


def test_score_deterministic() -> None:
    model = _fitted_model()
    s1 = score_event(model, _event(42.0))
    s2 = score_event(model, _event(42.0))
    assert s1 == s2


# ── is_anomaly ────────────────────────────────────────────────────────────────


def test_is_anomaly_true_below_threshold() -> None:
    assert is_anomaly(score=-0.15, threshold=0.0) is True


def test_is_anomaly_false_above_threshold() -> None:
    assert is_anomaly(score=0.05, threshold=0.0) is False


def test_is_anomaly_equal_to_threshold_is_not_anomaly() -> None:
    # Boundary: score == threshold is NOT an anomaly (strict less-than)
    assert is_anomaly(score=0.0, threshold=0.0) is False


def test_spike_event_detected_as_anomaly_end_to_end() -> None:
    model = _fitted_model()
    score = score_event(model, _event(500.0))
    assert is_anomaly(score, threshold=0.0) is True


def test_normal_event_not_detected_as_anomaly_end_to_end() -> None:
    model = _fitted_model()
    score = score_event(model, _event(50.0))
    assert is_anomaly(score, threshold=0.0) is False

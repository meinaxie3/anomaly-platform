"""Unit tests for the evaluator module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from training.evaluator import evaluate, inject_anomalies


def _normal_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
            "value": rng.normal(loc=50.0, scale=5.0, size=n),
        }
    )


# ── inject_anomalies ─────────────────────────────────────────────────────────


def test_inject_anomalies_returns_correct_shapes() -> None:
    df = _normal_df(100)
    df_mod, y_true = inject_anomalies(df, fraction=0.05, seed=0)
    assert len(df_mod) == len(df)
    assert len(y_true) == len(df)


def test_inject_anomalies_correct_count() -> None:
    df = _normal_df(100)
    _, y_true = inject_anomalies(df, fraction=0.05, seed=0)
    # 5% of 100 = 5 anomalies
    assert y_true.sum() == 5


def test_inject_anomalies_values_are_spiked() -> None:
    df = _normal_df(100)
    df_mod, y_true = inject_anomalies(df, fraction=0.1, seed=1)
    anomaly_idx = np.where(y_true == 1)[0]
    for i in anomaly_idx:
        assert df_mod.iloc[i]["value"] > df.iloc[i]["value"]


def test_inject_anomalies_does_not_mutate_original() -> None:
    df = _normal_df(50)
    original_values = df["value"].tolist()
    inject_anomalies(df, fraction=0.1, seed=0)
    assert df["value"].tolist() == original_values


def test_inject_anomalies_empty_df() -> None:
    df = pd.DataFrame(columns=["timestamp", "value"])
    df_mod, y_true = inject_anomalies(df, fraction=0.05)
    assert len(df_mod) == 0
    assert len(y_true) == 0


def test_inject_anomalies_deterministic() -> None:
    df = _normal_df(200)
    _, y1 = inject_anomalies(df, seed=99)
    _, y2 = inject_anomalies(df, seed=99)
    np.testing.assert_array_equal(y1, y2)


# ── evaluate ─────────────────────────────────────────────────────────────────


def test_evaluate_perfect_predictions() -> None:
    # y_true: [1, 0, 0]  → model predicts -1, +1, +1 (perfect)
    y_true = np.array([1, 0, 0])
    y_pred_raw = np.array([-1, 1, 1])
    scores = evaluate(y_pred_raw, y_true)
    assert scores["precision"] == pytest.approx(1.0)
    assert scores["recall"] == pytest.approx(1.0)
    assert scores["f1"] == pytest.approx(1.0)


def test_evaluate_all_wrong() -> None:
    y_true = np.array([1, 1, 0, 0])
    y_pred_raw = np.array([1, 1, -1, -1])  # predicts anomaly for the normals
    scores = evaluate(y_pred_raw, y_true)
    assert scores["precision"] == pytest.approx(0.0)
    assert scores["recall"] == pytest.approx(0.0)


def test_evaluate_no_positive_labels_returns_sentinel() -> None:
    y_true = np.array([0, 0, 0])
    y_pred_raw = np.array([1, 1, 1])
    scores = evaluate(y_pred_raw, y_true)
    assert scores["precision"] == -1.0
    assert scores["recall"] == -1.0
    assert scores["f1"] == -1.0


def test_evaluate_keys_present() -> None:
    y_true = np.array([1, 0])
    y_pred_raw = np.array([-1, 1])
    scores = evaluate(y_pred_raw, y_true)
    assert set(scores.keys()) == {"precision", "recall", "f1"}

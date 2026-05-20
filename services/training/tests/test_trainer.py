"""Unit tests for the Isolation Forest trainer."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import IsolationForest
from training.trainer import deserialize, predict, serialize, train


def _df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
            "value": rng.normal(loc=50.0, scale=5.0, size=n),
        }
    )


# ── train ─────────────────────────────────────────────────────────────────────


def test_train_returns_fitted_model_and_time() -> None:
    model, fit_seconds = train(_df(), contamination=0.05)
    assert isinstance(model, IsolationForest)
    assert fit_seconds >= 0.0


def test_train_model_can_predict() -> None:
    df = _df()
    model, _ = train(df, contamination=0.05)
    preds = model.predict(df[["value"]].to_numpy())
    assert preds.shape == (len(df),)
    assert set(preds).issubset({-1, 1})


def test_train_raises_on_empty_df() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        train(pd.DataFrame(columns=["value"]))


def test_train_raises_on_missing_value_column() -> None:
    with pytest.raises(ValueError, match="'value' column"):
        train(pd.DataFrame({"timestamp": pd.date_range("2025-01-01", periods=5, freq="1min")}))


def test_train_is_deterministic() -> None:
    df = _df()
    model1, _ = train(df, random_state=0)
    model2, _ = train(df, random_state=0)
    preds1 = model1.predict(df[["value"]].to_numpy())
    preds2 = model2.predict(df[["value"]].to_numpy())
    np.testing.assert_array_equal(preds1, preds2)


# ── predict ───────────────────────────────────────────────────────────────────


def test_predict_returns_minus_one_or_one() -> None:
    df = _df()
    model, _ = train(df)
    preds = predict(model, df)
    assert set(preds).issubset({-1, 1})


# ── serialize / deserialize ───────────────────────────────────────────────────


def test_serialize_returns_bytes() -> None:
    model, _ = train(_df())
    data = serialize(model)
    assert isinstance(data, bytes)
    assert len(data) > 0


def test_serialize_deserialize_round_trip() -> None:
    df = _df()
    model, _ = train(df)
    data = serialize(model)
    restored = deserialize(data)
    assert isinstance(restored, IsolationForest)

    original_preds = predict(model, df)
    restored_preds = predict(restored, df)
    np.testing.assert_array_equal(original_preds, restored_preds)

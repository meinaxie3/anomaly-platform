"""Isolation Forest trainer and joblib serializer."""

from __future__ import annotations

import io
import time

import joblib
import numpy as np
import pandas as pd
from ap_logging import get_logger
from sklearn.ensemble import IsolationForest

log = get_logger(__name__)


def train(
    df: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
) -> tuple[IsolationForest, float]:
    """Fit an Isolation Forest on the ``value`` column of *df*.

    Args:
        df: DataFrame with a ``value`` column (float).
        contamination: Expected proportion of anomalies in the training data.
        random_state: Seed for reproducibility.

    Returns:
        (model, fit_seconds): The fitted model and wall-clock training time.

    Raises:
        ValueError: If *df* is empty or missing the ``value`` column.
    """
    if df.empty or "value" not in df.columns:
        raise ValueError("DataFrame must be non-empty and contain a 'value' column")

    X = df[["value"]].to_numpy()

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )

    t0 = time.monotonic()
    model.fit(X)
    fit_seconds = time.monotonic() - t0

    log.info(
        "model_trained",
        algorithm="isolation_forest",
        n_samples=len(X),
        contamination=contamination,
        fit_seconds=round(fit_seconds, 3),
    )
    return model, fit_seconds


def predict(model: IsolationForest, df: pd.DataFrame) -> np.ndarray:
    """Run inference on the ``value`` column of *df*.

    Returns raw Isolation Forest output: -1 = anomaly, +1 = normal.
    """
    X = df[["value"]].to_numpy()
    return model.predict(X)


def serialize(model: IsolationForest) -> bytes:
    """Serialize *model* to bytes using joblib compression."""
    buf = io.BytesIO()
    joblib.dump(model, buf, compress=3)
    return buf.getvalue()


def deserialize(data: bytes) -> IsolationForest:
    """Deserialize a joblib-encoded model from *data*."""
    buf = io.BytesIO(data)
    return joblib.load(buf)

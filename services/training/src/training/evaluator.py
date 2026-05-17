"""Holdout evaluation with synthetic anomaly injection."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score

from ap_logging import get_logger

log = get_logger(__name__)

# Anomalies are injected by multiplying the value by a random factor in this range.
_SPIKE_LOW = 5.0
_SPIKE_HIGH = 10.0


def inject_anomalies(
    df: pd.DataFrame,
    fraction: float = 0.05,
    seed: int = 0,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Randomly spike *fraction* of rows in *df* to simulate anomalies.

    Returns:
        df_modified: copy of *df* with spiked values
        y_true: int array of shape (len(df),) — 1 = anomaly, 0 = normal
    """
    if len(df) == 0:
        return df.copy(), np.array([], dtype=int)

    rng = np.random.default_rng(seed)
    n_anomalies = max(1, int(len(df) * fraction))
    anomaly_indices = rng.choice(len(df), size=n_anomalies, replace=False)

    df_mod = df.copy()
    spikes = rng.uniform(_SPIKE_LOW, _SPIKE_HIGH, size=n_anomalies)
    df_mod.iloc[anomaly_indices, df_mod.columns.get_loc("value")] *= spikes

    y_true = np.zeros(len(df), dtype=int)
    y_true[anomaly_indices] = 1

    log.debug(
        "anomalies_injected",
        n_total=len(df),
        n_anomalies=n_anomalies,
        fraction=fraction,
    )
    return df_mod, y_true


def evaluate(
    y_pred_raw: np.ndarray,
    y_true: np.ndarray,
) -> dict[str, float]:
    """Compute precision, recall, and F1 from Isolation Forest predictions.

    Isolation Forest uses the convention: -1 = anomaly, +1 = normal.
    We remap to: 1 = anomaly, 0 = normal before scoring.

    Args:
        y_pred_raw: raw output of ``model.predict(X)`` — values are -1 or +1
        y_true: ground-truth labels — 1 = anomaly, 0 = normal
    """
    # Remap: -1 → 1 (anomaly), +1 → 0 (normal)
    y_pred = np.where(y_pred_raw == -1, 1, 0).astype(int)

    # Guard against degenerate cases (e.g. no anomalies in tiny holdout)
    if y_true.sum() == 0:
        log.warning("evaluate_no_positive_labels")
        return {"precision": -1.0, "recall": -1.0, "f1": -1.0}

    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    log.info("evaluation_complete", precision=precision, recall=recall, f1=f1)
    return {"precision": precision, "recall": recall, "f1": f1}

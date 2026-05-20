"""Pure scoring functions — no I/O, fully unit-testable.

Isolation Forest's ``decision_function`` returns:
  - Negative values  → likely anomaly (the more negative, the more anomalous)
  - Positive values  → likely normal

We keep the raw score and the threshold used at scoring time so that historical
anomalies can be re-evaluated if the threshold is tuned later.
"""

from __future__ import annotations

from ap_schemas import MetricEvent
from sklearn.ensemble import IsolationForest


def score_event(model: IsolationForest, event: MetricEvent) -> float:
    """Return the raw Isolation Forest decision_function score for *event*.

    A score below the configured threshold indicates an anomaly.
    The score is deterministic given the same model and value.
    """
    return float(model.decision_function([[event.value]])[0])


def is_anomaly(score: float, threshold: float) -> bool:
    """Return True if *score* is below *threshold* (i.e. anomalous)."""
    return score < threshold

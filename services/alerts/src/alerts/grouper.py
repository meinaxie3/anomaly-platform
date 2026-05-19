"""Pure anomaly grouping function — no I/O, fully unit-testable.

Algorithm:
  1. Sort anomalies by (service, metric, timestamp).
  2. Group by (service, metric).
  3. Within each group: consecutive anomalies separated by <= grouping_window_secs
     belong to the same incident. A gap larger than the window starts a new one.
  4. Each incident's started_at = timestamp of its first anomaly.
"""

from __future__ import annotations

from datetime import timedelta
from itertools import groupby

from ap_schemas import AnomalyRecord, IncidentRecord


def group_into_incidents(
    anomalies: list[AnomalyRecord],
    grouping_window_secs: int = 600,
) -> list[tuple[IncidentRecord, list[AnomalyRecord]]]:
    """Group anomalies into incidents by time proximity per (service, metric).

    Returns a list of (incident, member_anomalies) tuples.
    An empty input returns an empty list.
    """
    if not anomalies:
        return []

    window = timedelta(seconds=grouping_window_secs)
    sorted_anomalies = sorted(anomalies, key=lambda a: (a.service, a.metric, a.timestamp))

    results: list[tuple[IncidentRecord, list[AnomalyRecord]]] = []

    for (service, metric), group_iter in groupby(
        sorted_anomalies, key=lambda a: (a.service, a.metric)
    ):
        group = list(group_iter)
        current_batch: list[AnomalyRecord] = [group[0]]

        for anomaly in group[1:]:
            gap = anomaly.timestamp - current_batch[-1].timestamp
            if gap <= window:
                current_batch.append(anomaly)
            else:
                results.append(_make_incident(service, metric, current_batch))
                current_batch = [anomaly]

        results.append(_make_incident(service, metric, current_batch))

    return results


def _make_incident(
    service: str,
    metric: str,
    members: list[AnomalyRecord],
) -> tuple[IncidentRecord, list[AnomalyRecord]]:
    incident = IncidentRecord(
        service=service,
        metric=metric,
        started_at=members[0].timestamp,
        anomaly_ids=[a.anomaly_id for a in members],
    )
    return incident, members

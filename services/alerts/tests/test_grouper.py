"""Unit tests for the anomaly grouper — pure function, no mocks needed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from alerts.grouper import group_into_incidents
from ap_schemas import AnomalyRecord

BASE_TIME = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


def _anomaly(
    service: str = "payment-api",
    metric: str = "cpu_percent",
    offset_mins: int = 0,
) -> AnomalyRecord:
    return AnomalyRecord(
        event_id=uuid4(),
        service=service,
        metric=metric,
        value=500.0,
        score=-0.3,
        threshold=0.0,
        model_id="model-1",
        timestamp=BASE_TIME + timedelta(minutes=offset_mins),
    )


def test_empty_anomalies_returns_empty() -> None:
    assert group_into_incidents([]) == []


def test_single_anomaly_creates_one_incident() -> None:
    result = group_into_incidents([_anomaly()])
    assert len(result) == 1
    incident, members = result[0]
    assert len(members) == 1
    assert incident.service == "payment-api"
    assert incident.metric == "cpu_percent"


def test_consecutive_within_window_merged_into_one_incident() -> None:
    # 3 anomalies at 0, 5, 9 minutes — all within 10-min window
    anomalies = [_anomaly(offset_mins=0), _anomaly(offset_mins=5), _anomaly(offset_mins=9)]
    result = group_into_incidents(anomalies, grouping_window_secs=600)
    assert len(result) == 1
    _, members = result[0]
    assert len(members) == 3


def test_consecutive_outside_window_creates_two_incidents() -> None:
    # Gap of 20 minutes between anomaly 1 and 2 → separate incidents
    anomalies = [_anomaly(offset_mins=0), _anomaly(offset_mins=20)]
    result = group_into_incidents(anomalies, grouping_window_secs=600)
    assert len(result) == 2


def test_different_service_metric_creates_separate_incidents() -> None:
    a1 = _anomaly(service="payment-api", metric="cpu_percent", offset_mins=0)
    a2 = _anomaly(service="auth-service", metric="latency_p99", offset_mins=0)
    result = group_into_incidents([a1, a2], grouping_window_secs=600)
    assert len(result) == 2
    services = {inc.service for inc, _ in result}
    assert services == {"payment-api", "auth-service"}


def test_incident_started_at_equals_first_anomaly_timestamp() -> None:
    anomalies = [_anomaly(offset_mins=0), _anomaly(offset_mins=3), _anomaly(offset_mins=6)]
    result = group_into_incidents(anomalies, grouping_window_secs=600)
    incident, _ = result[0]
    assert incident.started_at == BASE_TIME


def test_incident_anomaly_ids_match_members() -> None:
    anomalies = [_anomaly(offset_mins=0), _anomaly(offset_mins=2)]
    result = group_into_incidents(anomalies, grouping_window_secs=600)
    incident, members = result[0]
    assert set(incident.anomaly_ids) == {a.anomaly_id for a in members}


def test_mixed_within_and_outside_window() -> None:
    # 0, 5 → same incident | 25, 30 → new incident
    anomalies = [
        _anomaly(offset_mins=0),
        _anomaly(offset_mins=5),
        _anomaly(offset_mins=25),
        _anomaly(offset_mins=30),
    ]
    result = group_into_incidents(anomalies, grouping_window_secs=600)
    assert len(result) == 2
    _, m1 = result[0]
    _, m2 = result[1]
    assert len(m1) == 2
    assert len(m2) == 2

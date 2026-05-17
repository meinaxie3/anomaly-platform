"""Tests for MetricGenerator — determinism, counts, structure, anomaly flagging."""

from datetime import UTC, datetime, timedelta

import pytest
from ap_schemas import MetricEvent
from load_gen.anomaly import AnomalySpec, AnomalyType
from load_gen.generator import MetricGenerator
from load_gen.services import SERVICES

_UTC = UTC
_START = datetime(2025, 1, 6, 0, 0, 0, tzinfo=_UTC)  # Monday
_END = _START + timedelta(hours=2)
_INTERVAL = timedelta(minutes=10)


def _gen(**kwargs: object) -> MetricGenerator:
    return MetricGenerator(seed=42, **kwargs)  # type: ignore[arg-type]


# ── Determinism ───────────────────────────────────────────────────────────────


def test_same_seed_same_values() -> None:
    values1 = [e.value for e, _ in _gen().events(_START, _END, _INTERVAL)]
    values2 = [e.value for e, _ in _gen().events(_START, _END, _INTERVAL)]
    assert values1 == values2


def test_different_seeds_different_values() -> None:
    gen_a = MetricGenerator(seed=1)
    gen_b = MetricGenerator(seed=2)
    vals_a = [e.value for e, _ in gen_a.events(_START, _END, _INTERVAL)]
    vals_b = [e.value for e, _ in gen_b.events(_START, _END, _INTERVAL)]
    assert vals_a != vals_b


# ── Event count ───────────────────────────────────────────────────────────────


def test_event_count_matches_generator() -> None:
    gen = _gen()
    events = list(gen.events(_START, _END, _INTERVAL))
    assert len(events) == gen.event_count(_START, _END, _INTERVAL)


def test_event_count_formula() -> None:
    gen = _gen()
    # 2 hours / 10 min = 12 ticks; 5 services x 7 metrics = 35 per tick
    assert gen.event_count(_START, _END, _INTERVAL) == 12 * 35


def test_empty_window_produces_no_events() -> None:
    events = list(_gen().events(_START, _START, _INTERVAL))
    assert events == []


# ── Structure ─────────────────────────────────────────────────────────────────


def test_first_event_timestamp_is_start() -> None:
    event, _ = next(_gen().events(_START, _END, _INTERVAL))
    assert event.timestamp == _START


def test_all_events_are_metric_events() -> None:
    for event, _ in _gen().events(_START, _END, _INTERVAL):
        assert isinstance(event, MetricEvent)


def test_all_services_represented() -> None:
    events = [e for e, _ in _gen().events(_START, _END, _INTERVAL)]
    assert {e.service for e in events} == set(SERVICES)


def test_all_metrics_represented_per_service() -> None:
    events = [e for e, _ in _gen().events(_START, _END, _INTERVAL)]
    for service, metrics in SERVICES.items():
        seen = {e.metric for e in events if e.service == service}
        assert seen == set(metrics), f"{service}: missing metrics {set(metrics) - seen}"


def test_values_are_non_negative() -> None:
    for event, _ in _gen().events(_START, _END, _INTERVAL):
        assert event.value >= 0.0, f"{event.service}/{event.metric} = {event.value}"


# ── Anomaly flagging ──────────────────────────────────────────────────────────


def test_no_anomalies_without_specs() -> None:
    flags = [flag for _, flag in _gen().events(_START, _END, _INTERVAL)]
    assert not any(flags)


def test_anomaly_flagged_inside_window() -> None:
    window_start = _START + timedelta(minutes=10)
    spec = AnomalySpec(
        service="payment-api",
        metric="cpu_percent",
        anomaly_type=AnomalyType.SPIKE,
        start=window_start,
        duration=timedelta(minutes=10),
        magnitude=5.0,
    )
    gen = _gen(anomaly_specs=[spec])
    flagged = [(e, f) for e, f in gen.events(_START, _END, _INTERVAL) if f]
    assert len(flagged) > 0
    for event, _ in flagged:
        assert event.service == "payment-api"
        assert event.metric == "cpu_percent"


def test_anomaly_not_flagged_outside_window() -> None:
    # Window starts at hour 1 — first tick (t=0) must NOT be flagged
    spec = AnomalySpec(
        service="payment-api",
        metric="cpu_percent",
        anomaly_type=AnomalyType.SPIKE,
        start=_START + timedelta(hours=1),
        duration=timedelta(minutes=10),
        magnitude=5.0,
    )
    gen = _gen(anomaly_specs=[spec])
    first_tick_flags = [
        flag
        for event, flag in gen.events(_START, _END, _INTERVAL)
        if event.timestamp == _START
        and event.service == "payment-api"
        and event.metric == "cpu_percent"
    ]
    assert first_tick_flags == [False]


def test_anomaly_value_differs_from_baseline() -> None:
    window_start = _START + timedelta(minutes=10)
    spec = AnomalySpec(
        service="api-gateway",
        metric="request_rate",
        anomaly_type=AnomalyType.SPIKE,
        start=window_start,
        duration=timedelta(minutes=10),
        magnitude=10.0,
    )
    baseline = _gen()
    anomalous = _gen(anomaly_specs=[spec])

    def _value_at(gen: MetricGenerator, ts: datetime) -> float:
        for event, _ in gen.events(_START, _END, _INTERVAL):
            if (
                event.timestamp == ts
                and event.service == "api-gateway"
                and event.metric == "request_rate"
            ):
                return event.value
        pytest.fail("event not found")

    ts = window_start
    assert _value_at(anomalous, ts) != pytest.approx(_value_at(baseline, ts))

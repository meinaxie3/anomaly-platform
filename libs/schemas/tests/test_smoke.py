"""Smoke tests for ap-schemas — verifies schema round-trips and defaults."""

from datetime import UTC, datetime

from ap_schemas import AnomalyRecord, MetricEvent, MetricType, ModelMetadata


def test_metric_event_defaults() -> None:
    event = MetricEvent(
        service="payment-api",
        metric=MetricType.CPU_PERCENT,
        value=72.5,
        timestamp=datetime.now(tz=UTC),
    )
    assert event.event_id is not None
    assert event.labels == {}


def test_metric_event_json_round_trip() -> None:
    event = MetricEvent(
        service="auth-service",
        metric=MetricType.LATENCY_P99,
        value=312.0,
        timestamp=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        labels={"region": "us-east-1"},
    )
    restored = MetricEvent.model_validate_json(event.model_dump_json())
    assert restored.service == event.service
    assert restored.value == event.value
    assert restored.labels == event.labels


def test_model_metadata_defaults_and_round_trip() -> None:
    now = datetime.now(tz=UTC)
    meta = ModelMetadata(
        service="payment-api",
        metric="cpu_percent",
        algorithm="isolation_forest",
        trained_at=now,
        window_start=now,
        window_end=now,
        n_samples=1000,
        fit_seconds=0.42,
        eval_precision=0.9,
        eval_recall=0.8,
        eval_f1=0.847,
        artifact_path="models/payment-api/cpu_percent/abc.joblib",
    )
    assert meta.model_id is not None
    assert meta.is_current is False
    restored = ModelMetadata.model_validate_json(meta.model_dump_json())
    assert restored.model_id == meta.model_id
    assert restored.eval_f1 == meta.eval_f1


def test_anomaly_record_defaults() -> None:
    import uuid

    record = AnomalyRecord(
        event_id=uuid.uuid4(),
        service="payment-api",
        metric=MetricType.ERROR_RATE,
        value=0.12,
        score=-0.45,
        threshold=-0.3,
        model_id="model-v1",
        timestamp=datetime.now(tz=UTC),
    )
    assert record.resolved is False
    assert record.anomaly_id is not None

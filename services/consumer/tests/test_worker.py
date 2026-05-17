"""Unit tests for the consumer worker — no Redis or Postgres needed."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from ap_schemas import MetricEvent
from consumer.worker import parse_message


def _make_event(**kwargs) -> MetricEvent:  # type: ignore[no-untyped-def]
    defaults = dict(
        service="payment-api",
        metric="cpu_percent",
        value=55.0,
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    return MetricEvent(**(defaults | kwargs))


def _encode(event: MetricEvent) -> tuple[bytes, dict[bytes, bytes]]:
    return (b"1234-0", {b"data": event.model_dump_json().encode()})


def test_parse_valid_event_bytes() -> None:
    event = _make_event()
    result = parse_message(_encode(event))
    assert result is not None
    assert result.service == "payment-api"
    assert result.value == 55.0


def test_parse_valid_event_str_keys() -> None:
    event = _make_event(value=99.9)
    entry = ("1234-0", {"data": event.model_dump_json()})
    result = parse_message(entry)
    assert result is not None
    assert result.value == 99.9


def test_parse_preserves_event_id() -> None:
    event = _make_event()
    result = parse_message(_encode(event))
    assert result is not None
    assert result.event_id == event.event_id


def test_parse_missing_data_field_returns_none() -> None:
    result = parse_message((b"1234-0", {b"other_field": b"value"}))
    assert result is None


def test_parse_invalid_json_returns_none() -> None:
    result = parse_message((b"1234-0", {b"data": b"not-valid-json"}))
    assert result is None


def test_parse_missing_required_field_returns_none() -> None:
    incomplete = json.dumps({"service": "x", "metric": "y"}).encode()
    result = parse_message((b"1234-0", {b"data": incomplete}))
    assert result is None


def test_parse_with_labels() -> None:
    event = _make_event(labels={"region": "us-east-1", "env": "prod"})
    result = parse_message(_encode(event))
    assert result is not None
    assert result.labels == {"region": "us-east-1", "env": "prod"}


def test_parse_event_id_from_json() -> None:
    eid = uuid4()
    event = _make_event()
    event_dict = event.model_dump()
    event_dict["event_id"] = str(eid)
    raw = json.dumps(event_dict, default=str).encode()
    result = parse_message((b"9999-0", {b"data": raw}))
    assert result is not None
    assert result.event_id == eid

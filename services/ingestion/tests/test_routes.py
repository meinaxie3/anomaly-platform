"""Unit tests for ingestion routes — Redis is mocked, no network needed."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from ingestion.main import create_app


@pytest.fixture()
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1234-0")
    pipe = MagicMock()
    pipe.xadd = MagicMock()
    pipe.execute = AsyncMock(return_value=[])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


@pytest.fixture()
def client(mock_redis: MagicMock) -> Generator[TestClient, None, None]:
    app = create_app(redis_override=mock_redis)
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ingest_single_event(client: TestClient, mock_redis: MagicMock) -> None:
    payload = {
        "service": "payment-api",
        "metric": "cpu_percent",
        "value": 42.5,
        "timestamp": "2024-01-01T12:00:00Z",
    }
    resp = client.post("/ingest", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert "event_id" in body
    mock_redis.xadd.assert_called_once()


def test_ingest_batch_multiple_events(client: TestClient, mock_redis: MagicMock) -> None:
    events = [
        {
            "service": "auth-service",
            "metric": "request_rate",
            "value": 80.0,
            "timestamp": "2024-01-01T12:00:00Z",
        },
        {
            "service": "auth-service",
            "metric": "error_rate",
            "value": 0.01,
            "timestamp": "2024-01-01T12:00:00Z",
        },
    ]
    resp = client.post("/ingest/batch", json=events)
    assert resp.status_code == 202
    body = resp.json()
    assert body["count"] == 2
    assert body["status"] == "queued"
    assert mock_redis.pipeline.return_value.xadd.call_count == 2
    mock_redis.pipeline.return_value.execute.assert_called_once()


def test_ingest_batch_empty(client: TestClient, mock_redis: MagicMock) -> None:
    resp = client.post("/ingest/batch", json=[])
    assert resp.status_code == 202
    assert resp.json() == {"count": 0, "status": "queued"}
    mock_redis.pipeline.assert_not_called()


def test_ingest_rejects_invalid_payload(client: TestClient) -> None:
    resp = client.post("/ingest", json={"service": "x"})
    assert resp.status_code == 422


def test_ingest_batch_rejects_invalid_event(client: TestClient) -> None:
    resp = client.post("/ingest/batch", json=[{"service": "x"}])
    assert resp.status_code == 422

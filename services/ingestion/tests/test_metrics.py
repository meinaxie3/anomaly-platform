"""Tests for the Prometheus instrumentation on the ingestion service."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from ingestion.main import create_app


@pytest.fixture()
def mock_redis() -> MagicMock:
    redis = MagicMock()
    redis.xadd = AsyncMock(return_value=b"1234-0")
    redis.xlen = AsyncMock(return_value=42)
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


def test_metrics_endpoint_exists(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_metrics_endpoint_returns_prometheus_text(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert "text/plain" in resp.headers["content-type"]
    # Prometheus text format always starts with a comment or metric line
    assert resp.text.startswith("#") or "http_" in resp.text


def test_stream_depth_gauge_registered(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert "ingestion_stream_depth" in resp.text


def test_ingest_route_appears_in_metrics(client: TestClient, mock_redis: MagicMock) -> None:
    payload = {
        "service": "payment-api",
        "metric": "cpu_percent",
        "value": 55.0,
        "timestamp": "2024-01-01T12:00:00Z",
    }
    client.post("/ingest", json=payload)
    resp = client.get("/metrics")
    # The instrumentator records http_request_duration_seconds
    assert "http_request_duration_seconds" in resp.text

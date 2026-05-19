"""Unit tests for inference routes — no live DB or MinIO."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import IsolationForest

from inference.main import create_app
from inference.model_cache import ModelCache
from inference.settings import Settings


def _fitted_model(seed: int = 42) -> IsolationForest:
    rng = np.random.default_rng(seed)
    X = rng.normal(loc=50.0, scale=2.0, size=(500, 1))
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=seed)
    model.fit(X)
    return model


def _event_payload(value: float = 50.0) -> dict:
    return dict(
        service="payment-api",
        metric="cpu_percent",
        value=value,
        timestamp=datetime.now(tz=UTC).isoformat(),
        event_id=str(uuid4()),
    )


def _mock_pool() -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.executemany = AsyncMock(return_value="INSERT 0 1")
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _make_cache(model: IsolationForest | None) -> MagicMock:
    cache = MagicMock(spec=ModelCache)
    pair = (model, "model-id-abc") if model is not None else None
    cache.get_with_id = AsyncMock(return_value=pair)
    cache.get = AsyncMock(return_value=model)
    cache.invalidate_all = AsyncMock()
    cache.size = 1 if model else 0
    cache._cache = {}
    return cache


def _test_settings() -> Settings:
    return Settings(
        postgres_url="postgresql://x:x@localhost/x",
        inference_threshold=0.0,
        model_ttl_seconds=300,
    )


@pytest.fixture()
def client_with_model() -> Generator[TestClient, None, None]:
    model = _fitted_model()
    cache = _make_cache(model)
    pool = _mock_pool()
    app = create_app(settings=_test_settings(), pool_override=pool, cache_override=cache)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_no_model() -> Generator[TestClient, None, None]:
    cache = _make_cache(None)
    pool = _mock_pool()
    app = create_app(settings=_test_settings(), pool_override=pool, cache_override=cache)
    with TestClient(app) as c:
        yield c


# ── health ────────────────────────────────────────────────────────────────────


def test_health_returns_ok(client_with_model: TestClient) -> None:
    resp = client_with_model.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── /score ────────────────────────────────────────────────────────────────────


def test_score_empty_batch_returns_empty_list(client_with_model: TestClient) -> None:
    resp = client_with_model.post("/score", json=[])
    assert resp.status_code == 200
    assert resp.json() == []


def test_score_normal_events_returns_no_anomalies(client_with_model: TestClient) -> None:
    events = [_event_payload(value=50.0) for _ in range(5)]
    resp = client_with_model.post("/score", json=events)
    assert resp.status_code == 200
    assert resp.json() == []


def test_score_spike_event_returns_anomaly(client_with_model: TestClient) -> None:
    events = [_event_payload(value=500.0)]  # extreme spike
    resp = client_with_model.post("/score", json=events)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["score"] < 0.0
    assert body[0]["service"] == "payment-api"


def test_score_unknown_service_returns_empty_no_error(client_no_model: TestClient) -> None:
    resp = client_no_model.post("/score", json=[_event_payload()])
    assert resp.status_code == 200
    assert resp.json() == []


# ── /reload ───────────────────────────────────────────────────────────────────


def test_reload_invalidates_cache(client_with_model: TestClient) -> None:
    resp = client_with_model.post("/reload")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cache_flushed"

"""Unit tests for dashboard API routes -- no live DB required."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dashboard_api.main import create_app
from dashboard_api.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings() -> Settings:
    return Settings(
        postgres_url="postgresql://x:x@localhost/x",
        default_window_hours=3,
        max_window_days=30,
        aggregate_threshold_hours=2.0,
        max_raw_points=500,
    )


def _mock_pool(
    fetch_return: list | None = None,
    fetch_side_effect: list[list] | None = None,
    fetchrow_return: object = None,
) -> MagicMock:
    """Return a MagicMock asyncpg pool whose conn.fetch / conn.fetchrow are pre-wired.

    ``fetch_side_effect`` lets you return different rows on successive calls —
    useful for routes that call ``conn.fetch()`` twice in ``asyncio.gather``.
    """
    mock_conn = AsyncMock()
    if fetch_side_effect is not None:
        mock_conn.fetch = AsyncMock(side_effect=fetch_side_effect)
    else:
        mock_conn.fetch = AsyncMock(return_value=fetch_return or [])
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _client(pool: MagicMock) -> TestClient:
    app = create_app(settings=_settings(), pool_override=pool)
    return TestClient(app)


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_returns_ok() -> None:
    c = _client(_mock_pool())
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /services
# ---------------------------------------------------------------------------


def _service_row(
    service: str = "payment-api",
    open_incidents: int = 0,
    last_anomaly_at: datetime | None = None,
) -> dict:
    return {
        "service": service,
        "open_incidents": open_incidents,
        "last_anomaly_at": last_anomaly_at,
    }


def test_services_empty_db_returns_empty_list() -> None:
    c = _client(_mock_pool(fetch_return=[]))
    resp = c.get("/services")
    assert resp.status_code == 200
    assert resp.json() == []


def test_services_healthy_when_no_open_incidents() -> None:
    pool = _mock_pool(fetch_return=[_service_row("payment-api", open_incidents=0)])
    resp = _client(pool).get("/services")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["health"] == "healthy"
    assert body[0]["open_incidents"] == 0


def test_services_degraded_when_one_or_two_open_incidents() -> None:
    for n in (1, 2):
        pool = _mock_pool(fetch_return=[_service_row("svc", open_incidents=n)])
        body = _client(pool).get("/services").json()
        assert body[0]["health"] == "degraded", f"expected degraded for {n} incidents"


def test_services_critical_when_three_or_more_open_incidents() -> None:
    for n in (3, 10):
        pool = _mock_pool(fetch_return=[_service_row("svc", open_incidents=n)])
        body = _client(pool).get("/services").json()
        assert body[0]["health"] == "critical", f"expected critical for {n} incidents"


def test_services_returns_last_anomaly_at() -> None:
    ts = _now()
    pool = _mock_pool(fetch_return=[_service_row("svc", last_anomaly_at=ts)])
    body = _client(pool).get("/services").json()
    assert body[0]["last_anomaly_at"] is not None


# ---------------------------------------------------------------------------
# /metrics/{service}/{metric}
# ---------------------------------------------------------------------------


def _point_row(bucket: datetime | None = None) -> dict:
    return {
        "bucket": bucket or _now(),
        "avg_value": 55.0,
        "min_value": 50.0,
        "max_value": 60.0,
        "sample_count": 6,
    }


def _anomaly_row(ts: datetime | None = None) -> dict:
    return {"timestamp": ts or _now(), "value": 999.0, "score": -0.21}


def test_metric_series_returns_points_and_anomalies() -> None:
    # fetch_metric_series calls conn.fetch() twice via asyncio.gather:
    # first call = point rows, second call = anomaly rows.
    pool = _mock_pool(fetch_side_effect=[[_point_row()], [_anomaly_row()]])
    params = {
        "from": (_now() - timedelta(hours=1)).isoformat(),
        "to": _now().isoformat(),
    }
    resp = _client(pool).get("/metrics/payment-api/cpu_percent", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "payment-api"
    assert body["metric"] == "cpu_percent"
    assert len(body["points"]) == 1
    assert len(body["anomalies"]) == 1
    assert body["anomalies"][0]["score"] == pytest.approx(-0.21)


def test_metric_series_empty_window_returns_empty_lists() -> None:
    pool = _mock_pool(fetch_side_effect=[[], []])
    params = {
        "from": (_now() - timedelta(hours=1)).isoformat(),
        "to": _now().isoformat(),
    }
    resp = _client(pool).get("/metrics/payment-api/cpu_percent", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert body["points"] == []
    assert body["anomalies"] == []


def test_metric_series_rejects_future_to() -> None:
    params = {"to": (_now() + timedelta(hours=2)).isoformat()}
    resp = _client(_mock_pool()).get("/metrics/svc/m", params=params)
    assert resp.status_code == 400


def test_metric_series_rejects_from_too_far_back() -> None:
    params = {"from": (_now() - timedelta(days=60)).isoformat()}
    resp = _client(_mock_pool()).get("/metrics/svc/m", params=params)
    assert resp.status_code == 400


def test_metric_series_rejects_from_after_to() -> None:
    now = _now()
    params = {"from": now.isoformat(), "to": (now - timedelta(hours=1)).isoformat()}
    resp = _client(_mock_pool()).get("/metrics/svc/m", params=params)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /incidents
# ---------------------------------------------------------------------------


def _incident_row(status: str = "open") -> dict:
    return {
        "incident_id": uuid4(),
        "service": "payment-api",
        "metric": "cpu_percent",
        "status": status,
        "started_at": _now() - timedelta(minutes=30),
        "resolved_at": None,
        "anomaly_count": 3,
    }


def test_incidents_returns_list() -> None:
    pool = _mock_pool(fetch_return=[_incident_row("open")])
    resp = _client(pool).get("/incidents")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["service"] == "payment-api"
    assert body[0]["anomaly_count"] == 3


def test_incidents_empty_returns_empty_list() -> None:
    resp = _client(_mock_pool(fetch_return=[])).get("/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_incidents_filters_by_status() -> None:
    pool = _mock_pool(fetch_return=[_incident_row("resolved")])
    resp = _client(pool).get("/incidents?status=resolved")
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "resolved"


def test_incidents_rejects_invalid_status() -> None:
    resp = _client(_mock_pool()).get("/incidents?status=exploded")
    assert resp.status_code == 400


def test_incidents_rejects_limit_too_large() -> None:
    resp = _client(_mock_pool()).get("/incidents?limit=999")
    assert resp.status_code == 422  # FastAPI validation


# ---------------------------------------------------------------------------
# /models
# ---------------------------------------------------------------------------


def _model_row(service: str = "payment-api", is_current: bool = True) -> dict:
    return {
        "model_id": str(uuid4()),
        "service": service,
        "metric": "cpu_percent",
        "algorithm": "IsolationForest",
        "trained_at": _now() - timedelta(hours=2),
        "n_samples": 12500,
        "fit_seconds": 1.23,
        "eval_precision": -1.0,
        "eval_recall": -1.0,
        "eval_f1": -1.0,
        "is_current": is_current,
        "window_start": _now() - timedelta(days=7),
        "window_end": _now(),
    }


def test_models_returns_list() -> None:
    pool = _mock_pool(fetch_return=[_model_row()])
    resp = _client(pool).get("/models")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["algorithm"] == "IsolationForest"
    assert body[0]["eval_precision"] == pytest.approx(-1.0)
    assert body[0]["eval_recall"] == pytest.approx(-1.0)
    assert body[0]["eval_f1"] == pytest.approx(-1.0)


def test_models_empty_returns_empty_list() -> None:
    resp = _client(_mock_pool(fetch_return=[])).get("/models")
    assert resp.status_code == 200
    assert resp.json() == []


def test_models_current_only_param_accepted() -> None:
    pool = _mock_pool(fetch_return=[_model_row(is_current=True)])
    resp = _client(pool).get("/models?current_only=true")
    assert resp.status_code == 200
    assert resp.json()[0]["is_current"] is True


def test_models_filtered_by_service() -> None:
    pool = _mock_pool(fetch_return=[_model_row(service="auth-service")])
    resp = _client(pool).get("/models?service=auth-service")
    assert resp.status_code == 200
    assert resp.json()[0]["service"] == "auth-service"

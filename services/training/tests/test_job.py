"""Unit tests for the training job orchestrator — all I/O is mocked."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from training.job import _MIN_SAMPLES, _train_one, run_training_job
from training.settings import Settings
from training.store import ModelStore

NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        postgres_url="postgresql://x:x@localhost/x",
        minio_endpoint="http://localhost:9000",
        minio_access_key="minio",
        minio_secret_key="minio123",
        minio_bucket="models",
        training_window_days=30,
        holdout_fraction=0.2,
        contamination=0.05,
    )


def _mock_store() -> MagicMock:
    store = MagicMock(spec=ModelStore)
    store.upload.return_value = "models/svc/metric/id.joblib"
    store.artifact_key = ModelStore.artifact_key  # use the real static method
    return store


def _normal_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n, freq="1min"),
            "value": rng.normal(50.0, 5.0, size=n),
        }
    )


# ── run_training_job ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_training_job_trains_one_model_per_pair() -> None:
    pool = MagicMock()
    store = _mock_store()
    settings = _settings()

    df = _normal_df(100)
    pairs = [("payment-api", "cpu_percent"), ("auth-service", "latency_p99")]

    with (
        patch("training.job.loader.discover_pairs", new=AsyncMock(return_value=pairs)),
        patch("training.job.loader.load_series", new=AsyncMock(return_value=df)),
        patch("training.job.registry.register", new=AsyncMock()),
    ):
        results = await run_training_job(pool, store, settings)

    assert len(results) == 2
    assert store.upload.call_count == 2


@pytest.mark.asyncio
async def test_run_training_job_no_pairs_returns_empty() -> None:
    pool = MagicMock()
    store = _mock_store()

    with patch("training.job.loader.discover_pairs", new=AsyncMock(return_value=[])):
        results = await run_training_job(pool, store, _settings())

    assert results == []


@pytest.mark.asyncio
async def test_run_training_job_skips_insufficient_data() -> None:
    pool = MagicMock()
    store = _mock_store()

    tiny_df = _normal_df(_MIN_SAMPLES - 1)
    pairs = [("payment-api", "cpu_percent")]

    with (
        patch("training.job.loader.discover_pairs", new=AsyncMock(return_value=pairs)),
        patch("training.job.loader.load_series", new=AsyncMock(return_value=tiny_df)),
    ):
        results = await run_training_job(pool, store, _settings())

    assert results == []
    store.upload.assert_not_called()


# ── _train_one ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_train_one_returns_metadata_with_correct_fields() -> None:
    pool = MagicMock()
    store = _mock_store()
    settings = _settings()
    window_start = NOW - timedelta(days=30)

    with (
        patch("training.job.loader.load_series", new=AsyncMock(return_value=_normal_df(100))),
        patch("training.job.registry.register", new=AsyncMock()),
    ):
        meta = await _train_one(
            pool, store, settings, "payment-api", "cpu_percent", window_start, NOW
        )

    assert meta is not None
    assert meta.service == "payment-api"
    assert meta.metric == "cpu_percent"
    assert meta.algorithm == "isolation_forest"
    assert meta.n_samples > 0
    assert meta.artifact_path.startswith("models/payment-api/cpu_percent/")
    assert meta.artifact_path.endswith(".joblib")


@pytest.mark.asyncio
async def test_train_one_artifact_key_contains_model_id() -> None:
    pool = MagicMock()
    store = _mock_store()
    window_start = NOW - timedelta(days=30)

    with (
        patch("training.job.loader.load_series", new=AsyncMock(return_value=_normal_df(100))),
        patch("training.job.registry.register", new=AsyncMock()),
    ):
        meta = await _train_one(pool, store, _settings(), "svc", "metric", window_start, NOW)

    assert meta is not None
    assert str(meta.model_id) in meta.artifact_path


@pytest.mark.asyncio
async def test_train_one_uploads_then_registers() -> None:
    """Upload must happen before registry.register is called."""
    pool = MagicMock()
    store = _mock_store()
    call_order: list[str] = []

    store.upload.side_effect = lambda *a, **kw: call_order.append("upload")
    mock_register = AsyncMock(side_effect=lambda *a, **kw: call_order.append("register"))
    window_start = NOW - timedelta(days=30)

    with (
        patch("training.job.loader.load_series", new=AsyncMock(return_value=_normal_df(100))),
        patch("training.job.registry.register", new=mock_register),
    ):
        await _train_one(pool, store, _settings(), "svc", "m", window_start, NOW)

    assert call_order == ["upload", "register"]

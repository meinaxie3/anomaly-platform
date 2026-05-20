"""Unit tests for ModelCache — MinIO and asyncpg are fully mocked."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest
from inference.model_cache import ModelCache, _CacheEntry
from sklearn.ensemble import IsolationForest
from training.store import ModelStore
from training.trainer import serialize


def _fitted_model() -> IsolationForest:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({"value": rng.normal(50, 5, 200)})
    model = IsolationForest(n_estimators=10, random_state=42)
    model.fit(df[["value"]].to_numpy())
    return model


def _make_pool(row: object) -> MagicMock:
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=row)
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


def _make_store(model: IsolationForest | None = None) -> MagicMock:
    store = MagicMock(spec=ModelStore)
    if model is not None:
        store.download.return_value = serialize(model)
    return store


@pytest.mark.asyncio
async def test_cache_miss_loads_from_minio() -> None:
    model = _fitted_model()
    row = {"model_id": "abc-123", "artifact_path": "models/svc/m/abc.joblib"}
    pool = _make_pool(row)
    store = _make_store(model)

    cache = ModelCache(store=store, pool=pool, ttl_seconds=300)
    result = await cache.get("svc", "m")

    assert result is not None
    assert isinstance(result, IsolationForest)
    store.download.assert_called_once_with("models/svc/m/abc.joblib")


@pytest.mark.asyncio
async def test_cache_hit_skips_minio() -> None:
    model = _fitted_model()
    row = {"model_id": "abc-123", "artifact_path": "models/svc/m/abc.joblib"}
    pool = _make_pool(row)
    store = _make_store(model)

    cache = ModelCache(store=store, pool=pool, ttl_seconds=300)
    await cache.get("svc", "m")  # first call — loads
    await cache.get("svc", "m")  # second call — should hit cache

    store.download.assert_called_once()  # only one download


@pytest.mark.asyncio
async def test_cache_expired_triggers_reload() -> None:
    model = _fitted_model()
    row = {"model_id": "abc-123", "artifact_path": "models/svc/m/abc.joblib"}
    pool = _make_pool(row)
    store = _make_store(model)

    cache = ModelCache(store=store, pool=pool, ttl_seconds=300)
    await cache.get("svc", "m")  # loads

    # Manually expire the cache entry
    cache._cache[("svc", "m")] = _CacheEntry(
        model=model, model_id="abc-123", loaded_at=time.monotonic() - 400
    )
    await cache.get("svc", "m")  # should reload

    assert store.download.call_count == 2


@pytest.mark.asyncio
async def test_cache_returns_none_when_no_model_in_registry() -> None:
    pool = _make_pool(None)  # no row in registry
    store = _make_store()

    cache = ModelCache(store=store, pool=pool, ttl_seconds=300)
    result = await cache.get("unknown-svc", "unknown-metric")

    assert result is None
    store.download.assert_not_called()


@pytest.mark.asyncio
async def test_invalidate_all_clears_cache() -> None:
    model = _fitted_model()
    row = {"model_id": "abc-123", "artifact_path": "models/svc/m/abc.joblib"}
    pool = _make_pool(row)
    store = _make_store(model)

    cache = ModelCache(store=store, pool=pool, ttl_seconds=300)
    await cache.get("svc", "m")  # loads and caches
    assert cache.size == 1

    await cache.invalidate_all()
    assert cache.size == 0

    await cache.get("svc", "m")  # must reload
    assert store.download.call_count == 2

"""Unit tests for the model registry — asyncpg is fully mocked."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ap_schemas import ModelMetadata
from training.registry import get_current, register, rollback_to

NOW = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_metadata(**overrides: object) -> ModelMetadata:
    defaults = dict(
        service="payment-api",
        metric="cpu_percent",
        algorithm="isolation_forest",
        trained_at=NOW,
        window_start=NOW,
        window_end=NOW,
        n_samples=800,
        fit_seconds=0.35,
        eval_precision=0.85,
        eval_recall=0.80,
        eval_f1=0.824,
        artifact_path="models/payment-api/cpu_percent/abc.joblib",
    )
    defaults.update(overrides)
    return ModelMetadata(**defaults)  # type: ignore[arg-type]


def _make_pool(fetchrow_return: object = None) -> MagicMock:
    """Build a mock asyncpg Pool.

    The pool supports both ``execute`` (fire-and-forget) and ``fetchrow``
    (query that returns one row), and wraps them in a transaction context.
    """
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow_return)

    # transaction() is a context manager
    mock_tx = AsyncMock()
    mock_tx.__aenter__ = AsyncMock(return_value=None)
    mock_tx.__aexit__ = AsyncMock(return_value=False)
    mock_conn.transaction = MagicMock(return_value=mock_tx)

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_pool


# ── register ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_clears_then_inserts() -> None:
    pool = _make_pool()
    meta = _make_metadata()
    await register(pool, meta)

    conn = pool.acquire.return_value.__aenter__.return_value
    assert conn.execute.call_count == 2
    # First call clears current; second inserts the new record
    first_sql = conn.execute.call_args_list[0].args[0]
    second_sql = conn.execute.call_args_list[1].args[0]
    assert "is_current = FALSE" in first_sql
    assert "INSERT INTO model_registry" in second_sql


@pytest.mark.asyncio
async def test_register_uses_transaction() -> None:
    pool = _make_pool()
    await register(pool, _make_metadata())
    conn = pool.acquire.return_value.__aenter__.return_value
    conn.transaction.assert_called_once()


# ── get_current ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_returns_none_when_missing() -> None:
    pool = _make_pool(fetchrow_return=None)
    result = await get_current(pool, "payment-api", "cpu_percent")
    assert result is None


@pytest.mark.asyncio
async def test_get_current_returns_metadata() -> None:
    model_id = uuid4()
    row = {
        "model_id": model_id,
        "service": "payment-api",
        "metric": "cpu_percent",
        "algorithm": "isolation_forest",
        "trained_at": NOW,
        "window_start": NOW,
        "window_end": NOW,
        "n_samples": 800,
        "fit_seconds": 0.35,
        "eval_precision": 0.85,
        "eval_recall": 0.80,
        "eval_f1": 0.824,
        "artifact_path": "models/payment-api/cpu_percent/abc.joblib",
        "is_current": True,
    }
    pool = _make_pool(fetchrow_return=row)
    result = await get_current(pool, "payment-api", "cpu_percent")
    assert result is not None
    assert result.model_id == model_id
    assert result.service == "payment-api"
    assert result.is_current is True


# ── rollback_to ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rollback_raises_when_model_not_found() -> None:
    pool = _make_pool(fetchrow_return=None)
    with pytest.raises(ValueError, match="not found in registry"):
        await rollback_to(pool, "payment-api", "cpu_percent", uuid4())


@pytest.mark.asyncio
async def test_rollback_clears_then_sets_current() -> None:
    model_id = uuid4()
    row = {"model_id": model_id}  # minimal — just needs to exist
    pool = _make_pool(fetchrow_return=row)
    await rollback_to(pool, "payment-api", "cpu_percent", model_id)

    conn = pool.acquire.return_value.__aenter__.return_value
    sqls = [c.args[0] for c in conn.execute.call_args_list]
    assert any("is_current = FALSE" in s for s in sqls)
    assert any("is_current = TRUE" in s for s in sqls)

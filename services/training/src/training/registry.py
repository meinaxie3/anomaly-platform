"""Model registry — writes metadata to Postgres and manages the is_current pointer."""

from __future__ import annotations

from uuid import UUID

import asyncpg

from ap_logging import get_logger
from ap_schemas import ModelMetadata

log = get_logger(__name__)

_INSERT = """
    INSERT INTO model_registry (
        model_id, service, metric, algorithm,
        trained_at, window_start, window_end,
        n_samples, fit_seconds,
        eval_precision, eval_recall, eval_f1,
        artifact_path, is_current
    ) VALUES (
        $1, $2, $3, $4,
        $5, $6, $7,
        $8, $9,
        $10, $11, $12,
        $13, $14
    )
"""

_CLEAR_CURRENT = """
    UPDATE model_registry
    SET    is_current = FALSE
    WHERE  service = $1 AND metric = $2 AND is_current = TRUE
"""

_SET_CURRENT = """
    UPDATE model_registry
    SET    is_current = TRUE
    WHERE  model_id = $1
"""

_SELECT_CURRENT = """
    SELECT *
    FROM   model_registry
    WHERE  service = $1 AND metric = $2 AND is_current = TRUE
    LIMIT  1
"""

_SELECT_BY_ID = """
    SELECT *
    FROM   model_registry
    WHERE  model_id = $1
"""


async def register(pool: asyncpg.Pool, metadata: ModelMetadata) -> None:
    """Insert a new model record and mark it as the current model.

    Uses a transaction to atomically:
      1. Clear any existing is_current flag for this (service, metric) pair.
      2. Insert the new record with is_current=True.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(_CLEAR_CURRENT, metadata.service, metadata.metric)
            await conn.execute(
                _INSERT,
                metadata.model_id,
                metadata.service,
                metadata.metric,
                metadata.algorithm,
                metadata.trained_at,
                metadata.window_start,
                metadata.window_end,
                metadata.n_samples,
                metadata.fit_seconds,
                metadata.eval_precision,
                metadata.eval_recall,
                metadata.eval_f1,
                metadata.artifact_path,
                True,  # is_current — new models are always current
            )
    log.info(
        "model_registered",
        model_id=str(metadata.model_id),
        service=metadata.service,
        metric=metadata.metric,
        eval_f1=metadata.eval_f1,
    )


async def get_current(
    pool: asyncpg.Pool,
    service: str,
    metric: str,
) -> ModelMetadata | None:
    """Return the current model metadata for a given (service, metric) pair."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_SELECT_CURRENT, service, metric)
    if row is None:
        return None
    return _row_to_metadata(row)


async def rollback_to(
    pool: asyncpg.Pool,
    service: str,
    metric: str,
    model_id: UUID,
) -> None:
    """Roll back the current model pointer to a specific *model_id*.

    Atomically clears the existing current flag and sets the target model as current.
    Raises ValueError if *model_id* does not exist in the registry.
    """
    async with pool.acquire() as conn:
        # Verify the target model exists
        row = await conn.fetchrow(_SELECT_BY_ID, model_id)
        if row is None:
            raise ValueError(f"model_id {model_id} not found in registry")

        async with conn.transaction():
            await conn.execute(_CLEAR_CURRENT, service, metric)
            await conn.execute(_SET_CURRENT, model_id)

    log.info(
        "model_rolled_back",
        service=service,
        metric=metric,
        model_id=str(model_id),
    )


def _row_to_metadata(row: asyncpg.Record) -> ModelMetadata:
    return ModelMetadata(
        model_id=row["model_id"],
        service=row["service"],
        metric=row["metric"],
        algorithm=row["algorithm"],
        trained_at=row["trained_at"],
        window_start=row["window_start"],
        window_end=row["window_end"],
        n_samples=row["n_samples"],
        fit_seconds=row["fit_seconds"],
        eval_precision=row["eval_precision"],
        eval_recall=row["eval_recall"],
        eval_f1=row["eval_f1"],
        artifact_path=row["artifact_path"],
        is_current=row["is_current"],
    )

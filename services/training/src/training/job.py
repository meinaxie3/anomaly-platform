"""Training job orchestrator — discovers pairs, trains models, registers them."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import asyncpg
from ap_logging import get_logger
from ap_schemas import ModelMetadata

from training import evaluator, loader, registry, trainer
from training.settings import Settings
from training.store import ModelStore

log = get_logger(__name__)

_MIN_SAMPLES = 10  # skip training if fewer than this many rows are available


async def run_training_job(
    pool: asyncpg.Pool,
    store: ModelStore,
    settings: Settings,
) -> list[ModelMetadata]:
    """Train one Isolation Forest model per discovered (service, metric) pair.

    Steps per pair:
      1. Load the full training window from TimescaleDB.
      2. Split into train (first 80%) and holdout (last 20%) windows.
      3. Inject synthetic anomalies into holdout.
      4. Fit Isolation Forest on the training split.
      5. Evaluate on the holdout → precision/recall/F1.
      6. Serialize → upload to MinIO.
      7. Register metadata in Postgres.

    Returns the list of all successfully trained ModelMetadata objects.
    """
    now = datetime.now(tz=UTC)
    window_start = now - timedelta(days=settings.training_window_days)

    pairs = await loader.discover_pairs(pool, since=window_start)
    if not pairs:
        log.warning("no_pairs_found", since=window_start.isoformat())
        return []

    log.info("training_job_started", n_pairs=len(pairs), window_days=settings.training_window_days)
    results: list[ModelMetadata] = []

    for service, metric in pairs:
        meta = await _train_one(pool, store, settings, service, metric, window_start, now)
        if meta is not None:
            results.append(meta)

    log.info(
        "training_job_complete",
        trained=len(results),
        skipped=len(pairs) - len(results),
    )
    return results


async def _train_one(
    pool: asyncpg.Pool,
    store: ModelStore,
    settings: Settings,
    service: str,
    metric: str,
    window_start: datetime,
    window_end: datetime,
) -> ModelMetadata | None:
    """Train and register a single model. Returns None if skipped."""
    df = await loader.load_series(pool, service, metric, window_start, window_end)

    if len(df) < _MIN_SAMPLES:
        log.warning(
            "insufficient_data_skipped",
            service=service,
            metric=metric,
            n_rows=len(df),
            min_required=_MIN_SAMPLES,
        )
        return None

    # Split: first (1 - holdout_fraction) for training, remainder for evaluation
    split_idx = math.ceil(len(df) * (1 - settings.holdout_fraction))
    df_train = df.iloc[:split_idx].reset_index(drop=True)
    df_holdout = df.iloc[split_idx:].reset_index(drop=True)

    # Fit
    model, fit_seconds = trainer.train(df_train, contamination=settings.contamination)

    # Evaluate on holdout with synthetic anomalies
    df_holdout_injected, y_true = evaluator.inject_anomalies(df_holdout, seed=42)
    y_pred_raw = trainer.predict(model, df_holdout_injected)
    scores = evaluator.evaluate(y_pred_raw, y_true)

    # Generate model_id first so it can be used in the artifact key
    model_id = uuid4()
    artifact_key = ModelStore.artifact_key(service, metric, str(model_id))

    # Serialize and upload to MinIO
    artifact_bytes = trainer.serialize(model)
    store.upload(artifact_key, artifact_bytes)

    # Build metadata and register in Postgres (sets is_current=True atomically)
    meta = ModelMetadata(
        model_id=model_id,
        service=service,
        metric=metric,
        algorithm="isolation_forest",
        trained_at=window_end,
        window_start=window_start,
        window_end=window_end,
        n_samples=len(df_train),
        fit_seconds=fit_seconds,
        eval_precision=scores["precision"],
        eval_recall=scores["recall"],
        eval_f1=scores["f1"],
        artifact_path=artifact_key,
        is_current=False,  # registry.register() sets this to True atomically
    )
    await registry.register(pool, meta)

    log.info(
        "model_trained_and_registered",
        service=service,
        metric=metric,
        model_id=str(model_id),
        n_train=len(df_train),
        n_holdout=len(df_holdout),
        fit_seconds=round(fit_seconds, 3),
        **{f"eval_{k}": round(v, 4) for k, v in scores.items()},
    )
    return meta

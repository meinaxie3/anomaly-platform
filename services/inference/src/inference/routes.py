"""Inference API routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ap_logging import get_logger
from ap_schemas import AnomalyRecord, MetricEvent

from inference.db import batch_insert_anomalies
from inference.scorer import is_anomaly, score_event

log = get_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    cache = request.app.state.model_cache
    return {"status": "ok", "cached_models": cache.size}


@router.post("/score", response_model=list[AnomalyRecord])
async def score_batch(events: list[MetricEvent], request: Request) -> list[AnomalyRecord]:
    """Score a batch of metric events.

    Returns only the events that were classified as anomalies.
    Events whose (service, metric) pair has no trained model are silently skipped.
    """
    cache = request.app.state.model_cache
    pool = request.app.state.pool
    settings = request.app.state.settings
    threshold = settings.inference_threshold

    anomalies: list[AnomalyRecord] = []

    for event in events:
        result = await cache.get_with_id(event.service, event.metric)
        if result is None:
            log.debug("no_model_skip", service=event.service, metric=event.metric)
            continue

        model, model_id = result
        raw_score = score_event(model, event)
        if not is_anomaly(raw_score, threshold):
            continue

        anomalies.append(
            AnomalyRecord(
                event_id=event.event_id,
                service=event.service,
                metric=event.metric,
                value=event.value,
                score=raw_score,
                threshold=threshold,
                model_id=model_id,
                timestamp=event.timestamp,
            )
        )

    if anomalies:
        await batch_insert_anomalies(pool, anomalies)
        log.info(
            "batch_scored",
            total=len(events),
            anomalies=len(anomalies),
        )

    return anomalies


@router.post("/reload", status_code=200)
async def reload_models(request: Request) -> dict[str, str]:
    """Flush the in-memory model cache.

    The next scoring request will reload models from MinIO.
    Call this after a training run completes.
    """
    cache = request.app.state.model_cache
    await cache.invalidate_all()
    return {"status": "cache_flushed"}

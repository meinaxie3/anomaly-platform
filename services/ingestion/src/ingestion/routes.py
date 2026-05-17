from typing import cast

from ap_schemas import MetricEvent
from fastapi import APIRouter, Depends, Request, status
from redis.asyncio import Redis

from ingestion.settings import get_settings

router = APIRouter()


async def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest(
    event: MetricEvent,
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    stream = get_settings().stream_name
    await redis.xadd(stream, {"data": event.model_dump_json()})
    return {"event_id": str(event.event_id), "status": "queued"}


@router.post("/ingest/batch", status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(
    events: list[MetricEvent],
    redis: Redis = Depends(get_redis),
) -> dict[str, int | str]:
    if not events:
        return {"count": 0, "status": "queued"}

    stream = get_settings().stream_name
    pipe = redis.pipeline(transaction=False)
    for event in events:
        pipe.xadd(stream, {"data": event.model_dump_json()})
    await pipe.execute()
    return {"count": len(events), "status": "queued"}

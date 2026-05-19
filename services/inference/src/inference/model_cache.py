"""In-memory model cache with TTL-based reload from MinIO.

Models are keyed by (service, metric). On cache miss or TTL expiry the cache
queries model_registry for the current model_id, downloads the artifact from
MinIO, and deserializes it with joblib — all under a per-key asyncio.Lock so
concurrent requests don't trigger duplicate downloads.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import asyncpg
from sklearn.ensemble import IsolationForest

from ap_logging import get_logger
from training.store import ModelStore
from training.trainer import deserialize

if TYPE_CHECKING:
    pass

log = get_logger(__name__)

_REGISTRY_QUERY = """
    SELECT model_id, artifact_path
    FROM   model_registry
    WHERE  service = $1 AND metric = $2 AND is_current = TRUE
    LIMIT  1
"""


@dataclass
class _CacheEntry:
    model: IsolationForest
    model_id: str
    loaded_at: float = field(default_factory=time.monotonic)


class ModelCache:
    """Thread-safe in-memory cache of fitted IsolationForest models."""

    def __init__(self, store: ModelStore, pool: asyncpg.Pool, ttl_seconds: int = 300) -> None:
        self._store = store
        self._pool = pool
        self._ttl = ttl_seconds
        self._cache: dict[tuple[str, str], _CacheEntry] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_with_id(self, service: str, metric: str) -> tuple[IsolationForest, str] | None:
        """Return ``(model, model_id)`` for *(service, metric)*, or ``None``."""
        key = (service, metric)
        result = await self.get(service, metric)
        if result is None:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        return entry.model, entry.model_id

    async def get(self, service: str, metric: str) -> IsolationForest | None:
        """Return the current model for *(service, metric)*, loading if needed.

        Returns ``None`` if no model is registered for this pair yet.
        """
        key = (service, metric)
        entry = self._cache.get(key)
        if entry is not None and time.monotonic() - entry.loaded_at < self._ttl:
            return entry.model

        # Acquire a per-key lock so only one coroutine loads at a time
        lock = await self._get_lock(key)
        async with lock:
            # Re-check after acquiring lock (another coroutine may have loaded)
            entry = self._cache.get(key)
            if entry is not None and time.monotonic() - entry.loaded_at < self._ttl:
                return entry.model
            return await self._load(key)

    async def invalidate(self, service: str, metric: str) -> None:
        """Remove a specific model from the cache."""
        self._cache.pop((service, metric), None)

    async def invalidate_all(self) -> None:
        """Flush the entire cache — next request reloads from MinIO."""
        self._cache.clear()
        log.info("model_cache_flushed")

    @property
    def size(self) -> int:
        return len(self._cache)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_lock(self, key: tuple[str, str]) -> asyncio.Lock:
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def _load(self, key: tuple[str, str]) -> IsolationForest | None:
        service, metric = key
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_REGISTRY_QUERY, service, metric)

        if row is None:
            log.debug("no_current_model", service=service, metric=metric)
            return None

        model_id = str(row["model_id"])
        artifact_path = row["artifact_path"]

        try:
            data = self._store.download(artifact_path)
            model = deserialize(data)
        except Exception as exc:
            log.error(
                "model_load_failed",
                service=service,
                metric=metric,
                artifact_path=artifact_path,
                error=str(exc),
            )
            return None

        self._cache[key] = _CacheEntry(model=model, model_id=model_id)
        log.info("model_loaded_into_cache", service=service, metric=metric, model_id=model_id)
        return model

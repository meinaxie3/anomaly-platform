"""
Output writers.

FileWriter        — streams MetricEvent objects to a JSONL file.
GroundTruthWriter — writes anomaly window records to a JSONL file.
HttpWriter        — POSTs events to the ingestion /ingest/batch endpoint in chunks.

Both FileWriter and HttpWriter are safe to use as context managers.
"""

import json
from pathlib import Path
from types import TracebackType
from typing import IO, Self

import httpx
from ap_logging import get_logger
from ap_schemas import MetricEvent

from load_gen.anomaly import AnomalySpec

log = get_logger(__name__)

_DEFAULT_BATCH_SIZE = 200


class FileWriter:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._fh: IO[str] | None = None
        self._count = 0

    def __enter__(self) -> Self:
        self._fh = self._path.open("w", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._fh:
            self._fh.close()

    def write(self, event: MetricEvent) -> None:
        assert self._fh is not None, "FileWriter must be used as a context manager"
        self._fh.write(event.model_dump_json() + "\n")
        self._count += 1

    @property
    def count(self) -> int:
        return self._count


class HttpWriter:
    """
    Buffers MetricEvents and flushes to the ingestion API in batches.

    Events are sent via POST /ingest/batch. A 4xx response is logged as a
    warning (invalid payload) and counted; a 5xx response raises so the caller
    can decide whether to abort or continue.
    """

    def __init__(self, base_url: str, batch_size: int = _DEFAULT_BATCH_SIZE) -> None:
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._buffer: list[MetricEvent] = []
        self._client: httpx.Client | None = None
        self._count = 0
        self._errors = 0

    def __enter__(self) -> Self:
        self._client = httpx.Client(base_url=self._base_url, timeout=10.0)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._buffer:
            self._flush()
        if self._client:
            self._client.close()

    def write(self, event: MetricEvent) -> None:
        assert self._client is not None, "HttpWriter must be used as a context manager"
        self._buffer.append(event)
        if len(self._buffer) >= self._batch_size:
            self._flush()

    def _flush(self) -> None:
        assert self._client is not None
        batch = self._buffer
        self._buffer = []
        payload = [json.loads(e.model_dump_json()) for e in batch]

        resp = self._client.post("/ingest/batch", json=payload)

        if resp.is_success:
            self._count += len(batch)
        elif 400 <= resp.status_code < 500:
            self._errors += len(batch)
            log.warning(
                "ingest_batch_client_error",
                status=resp.status_code,
                batch_size=len(batch),
                body=resp.text[:200],
            )
        else:
            resp.raise_for_status()

    @property
    def count(self) -> int:
        return self._count

    @property
    def errors(self) -> int:
        return self._errors


class GroundTruthWriter:
    """Writes the anomaly schedule so Phase 6 eval can compute precision/recall."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path

    def write_all(self, specs: list[AnomalySpec]) -> None:
        with self._path.open("w", encoding="utf-8") as fh:
            for spec in specs:
                record = {
                    "service": spec.service,
                    "metric": spec.metric,
                    "anomaly_type": str(spec.anomaly_type),
                    "start": spec.start.isoformat(),
                    "end": spec.end.isoformat(),
                    "duration_seconds": spec.duration.total_seconds(),
                    "magnitude": spec.magnitude,
                }
                fh.write(json.dumps(record) + "\n")

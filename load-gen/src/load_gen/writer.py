"""
Output writers.

FileWriter        — streams MetricEvent objects to a JSONL file.
GroundTruthWriter — writes anomaly window records to a JSONL file.

Both create parent directories automatically and are safe to use as
context managers.
"""

import json
from pathlib import Path
from types import TracebackType
from typing import IO, Self

from ap_schemas import MetricEvent

from load_gen.anomaly import AnomalySpec


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

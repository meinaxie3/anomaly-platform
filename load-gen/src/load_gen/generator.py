"""
MetricGenerator — core driver that combines signal + anomaly injection.

Usage:
    gen = MetricGenerator(seed=42, anomaly_specs=specs)
    for event, is_anomalous in gen.events(start, end, interval):
        writer.write(event)
        if is_anomalous:
            ground_truth_count += 1

Determinism guarantee: the same seed always produces the same sequence of
values because we iterate services and metrics in sorted order and use a
single seeded numpy Generator for all draws.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta

import numpy as np
from ap_schemas import MetricEvent

from load_gen.anomaly import AnomalySpec, apply_anomaly
from load_gen.services import SERVICES
from load_gen.signal import SignalConfig, sample


class MetricGenerator:
    def __init__(
        self,
        seed: int = 42,
        services: dict[str, dict[str, SignalConfig]] | None = None,
        anomaly_specs: list[AnomalySpec] | None = None,
    ) -> None:
        self._rng = np.random.default_rng(seed)
        self._services = services if services is not None else SERVICES
        self._anomaly_specs = anomaly_specs or []

    def events(
        self,
        start: datetime,
        end: datetime,
        interval: timedelta = timedelta(seconds=60),
    ) -> Iterator[tuple[MetricEvent, bool]]:
        """
        Yield (MetricEvent, is_anomalous) for every service x metric x tick.

        Events are ordered: timestamp → service name → metric name.
        The RNG advances in this same order so the seed is reproducible
        regardless of which services or metrics you inspect.
        """
        ts = start
        while ts < end:
            for service in sorted(self._services):
                for metric in sorted(self._services[service]):
                    config = self._services[service][metric]
                    value = sample(config, ts, self._rng)
                    is_anomalous = False

                    for spec in self._anomaly_specs:
                        if spec.service == service and spec.metric == metric:
                            value, is_anomalous = apply_anomaly(value, ts, spec)
                            if is_anomalous:
                                break  # first matching spec wins per tick

                    yield (
                        MetricEvent(
                            service=service,
                            metric=metric,
                            value=value,
                            timestamp=ts,
                        ),
                        is_anomalous,
                    )
            ts += interval

    def event_count(
        self,
        start: datetime,
        end: datetime,
        interval: timedelta = timedelta(seconds=60),
    ) -> int:
        """Expected total events without materialising the generator."""
        ticks = int((end - start).total_seconds() / interval.total_seconds())
        metrics_per_tick = sum(len(m) for m in self._services.values())
        return ticks * metrics_per_tick

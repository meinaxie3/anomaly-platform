"""Tests for Prometheus metric objects on the consumer service."""

from prometheus_client import REGISTRY


def _metric_names() -> set[str]:
    """Collect all sample names from the registry (includes _total suffix)."""
    names: set[str] = set()
    for metric in REGISTRY.collect():
        names.add(metric.name)
        for sample in metric.samples:
            names.add(sample.name)
    return names


def test_write_latency_histogram_registered() -> None:
    from consumer.metrics import write_latency  # noqa: F401

    names = _metric_names()
    assert "consumer_db_write_seconds" in names


def test_events_counters_registered() -> None:
    from consumer.metrics import events_inserted, events_skipped  # noqa: F401

    names = _metric_names()
    assert "consumer_events_inserted_total" in names
    assert "consumer_events_skipped_total" in names


def test_dead_letter_counter_registered() -> None:
    from consumer.metrics import events_dead_lettered  # noqa: F401

    names = _metric_names()
    assert "consumer_events_dead_lettered_total" in names

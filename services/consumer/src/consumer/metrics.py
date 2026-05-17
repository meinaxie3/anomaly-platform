"""
Prometheus metric objects for the consumer service.

Exposed on a separate HTTP port (default 9102) via prometheus_client.start_http_server
so there's no FastAPI dependency in the consumer.
"""

from prometheus_client import Counter, Histogram

write_latency = Histogram(
    "consumer_db_write_seconds",
    "Time spent in batch_insert per batch",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

events_inserted = Counter(
    "consumer_events_inserted_total",
    "Cumulative number of metric events written to TimescaleDB",
)

events_skipped = Counter(
    "consumer_events_skipped_total",
    "Cumulative number of duplicate events skipped (ON CONFLICT DO NOTHING)",
)

events_dead_lettered = Counter(
    "consumer_events_dead_lettered_total",
    "Cumulative number of events sent to the dead-letter stream after repeated DB failures",
)

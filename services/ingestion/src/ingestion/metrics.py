"""
Prometheus metric objects for the ingestion service.

Defined at module level so they are singletons — safe to import from tests
or multiple modules without double-registration errors.
"""

from prometheus_client import Gauge

stream_depth = Gauge(
    "ingestion_stream_depth",
    "Number of messages currently in the Redis metrics stream (XLEN)",
)

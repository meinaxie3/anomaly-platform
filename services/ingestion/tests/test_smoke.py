"""Smoke test — confirms workspace dependencies resolve correctly."""


def test_shared_libs_importable() -> None:
    import ap_logging  # noqa: F401
    import ap_schemas  # noqa: F401


def test_metric_event_importable() -> None:
    from ap_schemas import MetricEvent  # noqa: F401

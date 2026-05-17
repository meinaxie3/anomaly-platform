"""Smoke tests — workspace resolution + public API surface."""

from ap_schemas import MetricType


def test_shared_libs_importable() -> None:
    import ap_logging  # noqa: F401
    import ap_schemas  # noqa: F401


def test_metric_types_available() -> None:
    assert MetricType.CPU_PERCENT == "cpu_percent"
    assert MetricType.ERROR_RATE == "error_rate"


def test_generator_importable() -> None:
    from load_gen.generator import MetricGenerator  # noqa: F401


def test_services_catalog_shape() -> None:
    from load_gen.services import SERVICES

    assert len(SERVICES) == 5
    for service, metrics in SERVICES.items():
        assert len(metrics) == 7, f"{service} should have 7 metrics"


def test_anomaly_types_available() -> None:
    from load_gen.anomaly import AnomalyType

    assert set(AnomalyType) == {"spike", "dip", "level_shift", "gradual_drift"}

"""Smoke test — confirms workspace dependencies resolve correctly."""


def test_shared_libs_importable() -> None:
    import ap_logging  # noqa: F401
    import ap_schemas  # noqa: F401

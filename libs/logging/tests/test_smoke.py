"""Smoke tests for ap-logging."""

import logging

from ap_logging import configure_logging, get_logger


def test_configure_logging_dev() -> None:
    configure_logging(service="test-service", env="dev", level="WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_prod() -> None:
    configure_logging(service="test-service", env="prod", level="INFO")
    assert logging.getLogger().level == logging.INFO


def test_get_logger_returns_bound_logger() -> None:
    configure_logging(service="test-service", env="dev")
    log = get_logger(__name__)
    assert log is not None
    # Should not raise
    log.info("smoke_test_passed", result="ok")

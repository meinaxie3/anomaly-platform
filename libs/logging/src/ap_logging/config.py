"""
Structured logging configuration for all Anomaly Platform services.

Usage in any service:
    from ap_logging import configure_logging, get_logger

    configure_logging(service="ingestion", env="dev")
    log = get_logger(__name__)
    log.info("server_started", port=8001)
"""

import logging
import sys

import structlog


def configure_logging(
    service: str,
    env: str = "prod",
    level: str = "INFO",
) -> None:
    """Wire up structlog.

    - ENV=dev  → coloured, human-readable console output.
    - ENV=prod → newline-delimited JSON, one object per log record.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        # Inject service name into every log record.
        _inject_service(service),
    ]

    if env == "dev":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger — call this at module level in each file."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def _inject_service(service: str) -> structlog.types.Processor:
    def processor(
        logger: logging.Logger,
        method: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        event_dict["service"] = service
        return event_dict

    return processor

"""
Structured logging configuration using structlog
Provides JSON-formatted logs with request context for production observability
"""
import logging
import structlog
import os
from typing import Any
from datetime import datetime


def add_app_context(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Add application-level context to all log entries"""
    event_dict['app'] = 'parking-v5-api'
    event_dict['version'] = '5.8.0'
    event_dict['environment'] = os.getenv('ENVIRONMENT', 'production')
    return event_dict


def drop_color_message_key(logger: Any, method_name: str, event_dict: dict) -> dict:
    """
    Remove the 'color_message' key from the event dict.
    Structlog adds this key for colored output, but we don't need it in JSON logs.
    """
    event_dict.pop('color_message', None)
    return event_dict


def configure_logging(log_level: str = "INFO", json_logs: bool = True):
    """
    Configure structured logging for the application

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output JSON logs. If False, use human-readable format

    Returns:
        Configured structlog logger

    Usage:
        from src.logging_config import configure_logging
        logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))

        logger.info("reservation_created",
            tenant_id=tenant_id,
            space_id=space_id,
            reservation_id=str(reservation_id),
            start_time=start_time.isoformat()
        )
    """

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=[logging.StreamHandler()]
    )

    # Shared processors for both console and file outputs
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_app_context,
        drop_color_message_key,
    ]

    # Choose output format based on environment
    if json_logs:
        # Production: JSON logs for machine parsing (ELK, Loki, etc.)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: Human-readable console logs with colors
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure formatter for standard library logging compatibility
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    # Update root logger handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())

    return structlog.get_logger()


def get_logger(name: str = None):
    """
    Get a logger instance with optional name

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        Structlog logger instance

    Usage:
        from src.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("processing_started", task_id=123)
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


# Example usage patterns:
if __name__ == "__main__":
    # Example 1: JSON logs (production)
    logger = configure_logging("INFO", json_logs=True)
    logger.info("server_started", port=8000, workers=4)
    logger.warning("high_memory_usage", memory_mb=512, threshold_mb=400)

    # Example 2: Human-readable logs (development)
    logger_dev = configure_logging("DEBUG", json_logs=False)
    logger_dev.debug("database_query", query="SELECT * FROM spaces", duration_ms=45.3)
    logger_dev.error("authentication_failed", user_email="test@example.com", reason="invalid_password")

    # Example 3: With context variables
    structlog.contextvars.bind_contextvars(request_id="abc-123", tenant_id="tenant-xyz")
    logger.info("request_completed", status_code=200, duration_ms=125.4)
    # Output includes: request_id=abc-123, tenant_id=tenant-xyz
    structlog.contextvars.unbind_contextvars("request_id", "tenant_id")

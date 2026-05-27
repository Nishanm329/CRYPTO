"""
Structured JSON logging configuration for the backend.
Provides consistent, machine-readable logs for monitoring and debugging.
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict
import uuid


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class StructuredLogger:
    """Wrapper for structured logging with request context."""

    def __init__(self, name: str):
        """Initialize structured logger."""
        self.logger = logging.getLogger(name)
        self.request_id: str = str(uuid.uuid4())

    def set_request_id(self, request_id: str) -> None:
        """Set request ID for current context."""
        self.request_id = request_id

    def _log(
        self,
        level: int,
        message: str,
        path: str = None,
        method: str = None,
        status_code: int = None,
        duration_ms: float = None,
        extra_data: Dict[str, Any] = None,
        exc_info: bool = False,
    ) -> None:
        """Internal logging method."""
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=level,
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=exc_info,
        )

        # Attach context
        record.request_id = self.request_id
        if path:
            record.path = path
        if method:
            record.method = method
        if status_code is not None:
            record.status_code = status_code
        if duration_ms is not None:
            record.duration_ms = round(duration_ms, 2)
        if extra_data:
            record.extra_data = extra_data

        self.logger.handle(record)

    def info(
        self,
        message: str,
        path: str = None,
        method: str = None,
        status_code: int = None,
        duration_ms: float = None,
        **extra_data,
    ) -> None:
        """Log info level message."""
        self._log(
            logging.INFO,
            message,
            path=path,
            method=method,
            status_code=status_code,
            duration_ms=duration_ms,
            extra_data=extra_data or None,
        )

    def warning(self, message: str, **extra_data) -> None:
        """Log warning level message."""
        self._log(logging.WARNING, message, extra_data=extra_data or None)

    def error(self, message: str, exc_info: bool = False, **extra_data) -> None:
        """Log error level message."""
        self._log(
            logging.ERROR,
            message,
            exc_info=exc_info,
            extra_data=extra_data or None,
        )

    def debug(self, message: str, **extra_data) -> None:
        """Log debug level message."""
        self._log(logging.DEBUG, message, extra_data=extra_data or None)


def setup_logging(level: str = "INFO") -> None:
    """
    Configure structured JSON logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler with JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level))
    console_handler.setFormatter(JSONFormatter())

    root_logger.addHandler(console_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)

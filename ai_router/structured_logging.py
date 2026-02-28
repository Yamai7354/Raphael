"""
Structured Logging for AI Router.

Provides JSON-formatted logs with consistent fields for
observability, debugging, and replay.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


# =============================================================================
# JSON LOG FORMATTER
# =============================================================================


class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON with consistent structure.
    """

    STANDARD_FIELDS = [
        "timestamp",
        "level",
        "logger",
        "message",
        "task_id",
        "subtask_id",
        "node_id",
        "role",
        "duration_ms",
        "error",
        "version",
    ]

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add optional context fields
        for field in [
            "task_id",
            "subtask_id",
            "node_id",
            "role",
            "duration_ms",
            "error",
            "version",
            "event_type",
        ]:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Add any extra data
        if hasattr(record, "data") and record.data:
            log_data["data"] = record.data

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


# =============================================================================
# CONTEXT-AWARE LOGGER
# =============================================================================


class StructuredLogger:
    """
    Logger that maintains context (task_id, etc.) across calls.
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs) -> None:
        """Set context fields for subsequent log calls."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context fields."""
        self._context.clear()

    def _log(self, level: int, msg: str, **kwargs) -> None:
        """Log with merged context."""
        extra = {**self._context, **kwargs}
        self._logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs) -> None:
        self._log(logging.CRITICAL, msg, **kwargs)


# =============================================================================
# LOG CONFIGURATION
# =============================================================================


def configure_logging(
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    json_format: bool = True,
) -> None:
    """
    Configure root logger with JSON formatting.

    Args:
        log_file: Optional file path for log persistence
        level: Logging level (default INFO)
        json_format: Use JSON formatting (default True)
    """
    root_logger = logging.getLogger("ai_router")
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(f"Log file: {log_file}")


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(f"ai_router.{name}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def log_event(
    event_type: str,
    message: str,
    task_id: Optional[str] = None,
    subtask_id: Optional[str] = None,
    node_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    data: Optional[Dict[str, Any]] = None,
    level: int = logging.INFO,
) -> None:
    """
    Log a structured event with standard fields.
    """
    logger = logging.getLogger("ai_router.events")

    extra = {
        "event_type": event_type,
    }
    if task_id:
        extra["task_id"] = task_id
    if subtask_id:
        extra["subtask_id"] = subtask_id
    if node_id:
        extra["node_id"] = node_id
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    if data:
        extra["data"] = data

    logger.log(level, message, extra=extra)

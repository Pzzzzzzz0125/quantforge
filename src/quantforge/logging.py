"""Structured logging utilities for QuantForge."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Render a log record as a compact JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the core fields of a log record."""
        event: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info is not None:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure the root logger with one structured stderr handler."""
    resolved_level = _resolve_level(level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(resolved_level)


def _resolve_level(level: int | str) -> int:
    if isinstance(level, int):
        return level

    resolved_level = logging.getLevelNamesMapping().get(level.upper())
    if resolved_level is None:
        msg = f"Unknown log level: {level!r}"
        raise ValueError(msg)
    return resolved_level

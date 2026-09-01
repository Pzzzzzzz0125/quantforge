"""Tests for the structured logging foundation."""

import json
import logging

import pytest

from quantforge.logging import JsonFormatter, configure_logging


def test_json_formatter_emits_core_fields() -> None:
    record = logging.LogRecord(
        name="quantforge.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="foundation ready",
        args=(),
        exc_info=None,
    )

    event = json.loads(JsonFormatter().format(record))

    assert event == {
        "timestamp": event["timestamp"],
        "level": "INFO",
        "logger": "quantforge.test",
        "message": "foundation ready",
    }
    assert event["timestamp"].endswith("+00:00")


def test_configure_logging_is_idempotent() -> None:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level

    try:
        configure_logging("WARNING")
        configure_logging("INFO")

        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0].formatter, JsonFormatter)
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)
        root_logger.setLevel(original_level)


def test_configure_logging_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="Unknown log level"):
        configure_logging("verbose")

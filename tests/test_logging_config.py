"""Tests for :func:`discord_bot_core.logging_config.configure_logging`."""

import logging

import pytest

from discord_bot_core.logging_config import (
    HANDLER_NAME,
    LOG_FORMAT,
    LOG_LEVELS,
    configure_logging,
)


def _tagged_handlers() -> list[logging.Handler]:
    root = logging.getLogger()
    return [h for h in root.handlers if h.get_name() == HANDLER_NAME]


@pytest.fixture(autouse=True)
def _restore_root_logger() -> object:
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    yield
    for handler in list(root.handlers):
        if handler not in original_handlers:
            root.removeHandler(handler)
    root.setLevel(original_level)


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO", "dev")
    configure_logging("INFO", "dev")
    assert len(_tagged_handlers()) == 1


def test_level_applied_to_root_logger() -> None:
    configure_logging("DEBUG", "prod")
    assert logging.getLogger().level == logging.DEBUG


def test_format_string_matches() -> None:
    configure_logging("INFO", "dev")
    (handler,) = _tagged_handlers()
    assert isinstance(handler.formatter, logging.Formatter)
    assert handler.formatter._fmt == LOG_FORMAT


def test_invalid_level_raises_value_error() -> None:
    with pytest.raises(ValueError) as excinfo:
        configure_logging("LOUD", "dev")
    message = str(excinfo.value)
    for valid in LOG_LEVELS:
        assert valid in message


def test_handler_writes_to_stderr(capfd: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", "dev")
    logging.getLogger("discord_bot_core.test").info("hello %s", "world")
    captured = capfd.readouterr()
    assert captured.out == ""
    assert "discord_bot_core.test: hello world" in captured.err
    assert "INFO" in captured.err


def test_caplog_still_works(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("INFO", "dev")
    logger = logging.getLogger("discord_bot_core.test")
    with caplog.at_level(logging.INFO, logger="discord_bot_core.test"):
        logger.info("captured %s", "line")
    assert len(caplog.records) == 1
    assert caplog.records[0].getMessage() == "captured line"

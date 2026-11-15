"""Logging configuration for applications built on the library.

The library uses the standard library ``logging`` module only. Applications call
:func:`configure_logging` once, from ``CoreBot.launch()`` before the client starts.
The configuration is idempotent: calling it again replaces the library's own handler
instead of stacking a second one, and pytest's handlers (``caplog``) are left alone.
"""

import logging
import sys

__all__ = ["HANDLER_NAME", "LOG_FORMAT", "LOG_LEVELS", "configure_logging"]

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
"""Format string used by the library's stderr handler."""

HANDLER_NAME = "discord_bot_core"
"""Name tag on the handler, so a later call can find and replace it."""

LOG_LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
"""Log levels accepted by :func:`configure_logging`."""


def configure_logging(level: str, environment: str) -> None:
    """Configure logging on the root logger.

    Installs exactly one ``StreamHandler`` writing to ``sys.stderr`` on the root
    logger, tagged with :data:`HANDLER_NAME`. A second call replaces the previously
    installed tagged handler rather than adding another one; handlers installed by
    other tools (for example pytest's ``caplog``) are not touched.

    Args:
        level: The root logger level. One of :data:`LOG_LEVELS`.
        environment: The application environment (``dev`` or ``prod``). Accepted for
            the caller's convenience and for future use; the code path is the same.

    Raises:
        ValueError: If ``level`` is not one of :data:`LOG_LEVELS`.
    """
    normalised = level.upper()
    if normalised not in LOG_LEVELS:
        valid = ", ".join(LOG_LEVELS)
        msg = f"invalid log level {level!r}; expected one of: {valid}"
        raise ValueError(msg)

    root = logging.getLogger()
    for existing in list(root.handlers):
        if existing.get_name() == HANDLER_NAME:
            root.removeHandler(existing)

    handler = logging.StreamHandler(sys.stderr)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(normalised)

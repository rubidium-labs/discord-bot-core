"""Exception hierarchy shared by the core and the applications built on it.

Domain code raises these without importing discord.py; :class:`ErrorHandler` turns
them into user-visible replies. Applications subclass :class:`UserFacingError` for
their own expected failures (for example ``NotEnoughParticipants``).
"""

from typing import Any

from discord import app_commands


class CoreError(Exception):
    """Base class of every exception the core raises."""


class UserFacingError(CoreError):
    """An expected failure whose message is shown to the user who triggered it.

    The message is also logged at INFO, so it must not contain sensitive data. The
    core's own errors pass a catalog ``message_key`` too: the handler replies with
    that key translated to the invoking user's locale, while ``message`` stays the
    English text used for logging and as the fallback.

    Attributes:
        message: The text shown to the user when no ``message_key`` is set.
        message_key: The catalog key whose translation is shown instead, if any.
        format_args: Values for the ``{placeholder}`` fields of the key's text.
    """

    def __init__(
        self,
        message: str,
        *,
        message_key: str | None = None,
        format_args: dict[str, Any] | None = None,
    ) -> None:
        """Create the error.

        Args:
            message: The text shown to the user, or the English fallback text when
                ``message_key`` is set.
            message_key: A catalog key whose translation replaces ``message`` in the
                reply, keeping ``message`` as the logged/fallback text.
            format_args: Values for the ``{placeholder}`` fields of the key's text.
        """
        super().__init__(message)
        self.message = message
        self.message_key = message_key
        self.format_args = format_args or {}

    def __str__(self) -> str:
        """Return the user-visible message."""
        return self.message


class DatabaseNotConfiguredError(CoreError):
    """A database was used although none was configured (a programmer error)."""


class NoActiveSessionError(CoreError):
    """``get_session`` was called outside a ``@transactional`` command."""


class ExternalServiceError(CoreError):
    """An external service (HTTP API, third party) failed.

    Attributes:
        status: The HTTP status code, when the failure was an HTTP response.
    """

    def __init__(self, message: str = "", *, status: int | None = None) -> None:
        """Create the error.

        Args:
            message: A sanitised description (no query string, no headers).
            status: The HTTP status code, when known.
        """
        super().__init__(message)
        self.status = status


class OwnerOnlyError(app_commands.CheckFailure):
    """The command is restricted to the bot owner.

    Inherits from :class:`discord.app_commands.CheckFailure` so the generic check
    rules apply even if the handler is not involved.
    """

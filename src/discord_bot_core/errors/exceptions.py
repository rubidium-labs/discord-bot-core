"""Exception hierarchy shared by the core and the applications built on it.

Domain code raises these without importing discord.py; :class:`ErrorHandler` turns
them into user-visible replies. Applications subclass :class:`UserFacingError` for
their own expected failures (for example ``NotEnoughParticipants``).
"""

from discord import app_commands


class CoreError(Exception):
    """Base class of every exception the core raises."""


class UserFacingError(CoreError):
    """An expected failure whose message is shown to the user who triggered it.

    The message is also logged at INFO, so it must not contain sensitive data.

    Attributes:
        message: The text shown to the user.
    """

    def __init__(self, message: str) -> None:
        """Create the error.

        Args:
            message: The text shown to the user.
        """
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """Return the user-visible message."""
        return self.message


class DatabaseNotConfiguredError(CoreError):
    """A database was used although none was configured (a programmer error)."""


class NoActiveSessionError(CoreError):
    """``get_session`` was called outside a ``@transactional`` command."""


class ExternalServiceError(CoreError):
    """An external service (HTTP API, third party) failed."""


class OwnerOnlyError(app_commands.CheckFailure):
    """The command is restricted to the bot owner.

    Inherits from :class:`discord.app_commands.CheckFailure` so the generic check
    rules apply even if the handler is not involved.
    """

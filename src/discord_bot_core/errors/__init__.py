"""Error handling: the exception hierarchy and the single ``ErrorHandler``.

See :mod:`discord_bot_core.errors.handler` for the classification and reply logic.
"""

from discord_bot_core.errors.exceptions import (
    CoreError,
    DatabaseNotConfiguredError,
    ExternalServiceError,
    NoActiveSessionError,
    OwnerOnlyError,
    UserFacingError,
)
from discord_bot_core.errors.handler import ErrorHandler

__all__ = [
    "CoreError",
    "DatabaseNotConfiguredError",
    "ErrorHandler",
    "ExternalServiceError",
    "NoActiveSessionError",
    "OwnerOnlyError",
    "UserFacingError",
]

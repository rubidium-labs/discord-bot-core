"""Tests for the exception hierarchy."""

import pytest
from discord import app_commands

from discord_bot_core.errors import (
    CoreError,
    DatabaseNotConfiguredError,
    ExternalServiceError,
    NoActiveSessionError,
    OwnerOnlyError,
    UserFacingError,
)


def test_user_facing_error_message() -> None:
    error = UserFacingError("Not enough participants.")
    assert error.message == "Not enough participants."
    assert str(error) == "Not enough participants."
    assert isinstance(error, CoreError)


@pytest.mark.parametrize(
    "error_class",
    [DatabaseNotConfiguredError, NoActiveSessionError, ExternalServiceError],
)
def test_core_errors(error_class: type[CoreError]) -> None:
    assert issubclass(error_class, CoreError)


def test_owner_only_is_a_check_failure() -> None:
    assert issubclass(OwnerOnlyError, app_commands.CheckFailure)

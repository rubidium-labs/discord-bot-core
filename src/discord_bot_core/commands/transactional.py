"""One database session per command, from ``@transactional`` and ``get_session``.

The decorator opens ``interaction.client.database.transaction()`` around the command
body and stores the session on ``interaction.extras`` under a private sentinel key;
:func:`get_session` reads it back. The command's signature is untouched, so no session
parameter becomes a slash-command option (see design §12).

The module imports no SQLAlchemy at runtime: the session type is only needed by type
checkers, so it is imported under ``TYPE_CHECKING``.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any, Protocol

from discord_bot_core.errors import DatabaseNotConfiguredError, NoActiveSessionError

if TYPE_CHECKING:
    import discord
    from sqlalchemy.ext.asyncio import AsyncSession

SESSION_KEY: object = object()
"""Private sentinel key under which the command's session lives in ``extras``."""


class TransactionalDatabase(Protocol):
    """The part of ``Database`` the decorator uses: one transaction per command."""

    def transaction(self) -> AbstractAsyncContextManager[AsyncSession]:
        """Open a session that commits on success and rolls back on error."""
        ...


class _Client(Protocol):
    """The part of ``CoreBot`` the decorator reads."""

    database: TransactionalDatabase | None


class _Interaction(Protocol):
    """The part of ``discord.Interaction`` the decorator reads."""

    client: _Client
    extras: dict[Any, Any]


def transactional[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Run a command body inside one database transaction.

    The session is available through :func:`get_session`. ``Database.transaction()``
    commits on success, rolls back on any exception (including cancellation) and
    closes the session in every case.

    Args:
        func: The async command callback. The interaction must be its last
            positional argument (discord.py always calls it that way).

    Returns:
        A wrapper with the same signature as ``func``.

    Raises:
        TypeError: If ``func`` is not a coroutine function.

    Example:
        >>> @app_commands.command(name="draw")
        ... @transactional
        ... async def draw(interaction: discord.Interaction) -> None:
        ...     session = get_session(interaction)  # doctest: +SKIP
    """
    if not inspect.iscoroutinefunction(func):
        raise TypeError(
            f"@transactional requires an async function, got {func!r} "
            "(place it above the def, under @app_commands.command)"
        )
    try:
        sig = inspect.signature(func, eval_str=True)
    except NameError:
        sig = inspect.signature(func)

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        interaction: _Interaction = args[-1]  # type: ignore[assignment]
        database = interaction.client.database
        if database is None:
            raise DatabaseNotConfiguredError(
                "A @transactional command ran but no database is configured; "
                "set database_url."
            )
        async with database.transaction() as session:
            if SESSION_KEY in interaction.extras:
                # Nested @transactional call inside one command: reuse the
                # command's session (design §12: one session per command).
                return await func(*args, **kwargs)
            interaction.extras[SESSION_KEY] = session
            try:
                return await func(*args, **kwargs)
            finally:
                interaction.extras.pop(SESSION_KEY, None)

    wrapper.__signature__ = sig  # type: ignore[attr-defined]
    return wrapper


def get_session(interaction: discord.Interaction) -> AsyncSession:
    """Return the session of the ``@transactional`` command running ``interaction``.

    Args:
        interaction: The interaction passed to the command body.

    Returns:
        The command's one session; every call in the same command returns the same
        object.

    Raises:
        NoActiveSessionError: If called outside a ``@transactional`` command.
    """
    try:
        session: AsyncSession = interaction.extras[SESSION_KEY]
    except KeyError:
        raise NoActiveSessionError(
            "get_session() called outside a @transactional command"
        ) from None
    return session

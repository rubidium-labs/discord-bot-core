"""Command checks shared by the core's commands.

The checks raise :class:`~discord_bot_core.errors.OwnerOnlyError` (a
``CheckFailure``) so the error handler answers them like any other check failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

import discord

from discord_bot_core.errors import OwnerOnlyError


class _OwnerClient(Protocol):
    """The part of ``CoreBot`` the owner check reads."""

    def is_owner(self, user: discord.abc.User, /) -> Awaitable[bool]:
        """Return whether ``user`` is the bot owner."""
        ...


def owner_only() -> Callable[[discord.Interaction], Awaitable[bool]]:
    """Return a check that only lets the bot owner run the command.

    Use it under ``@app_commands.check``::

        @app_commands.command(name="sync")
        @app_commands.check(owner_only())
        async def sync(interaction: discord.Interaction) -> None: ...

    Returns:
        A coroutine predicate raising :class:`OwnerOnlyError` for non-owners.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        client: _OwnerClient = interaction.client  # type: ignore[assignment]
        if not await client.is_owner(interaction.user):
            raise OwnerOnlyError()
        return True

    return predicate

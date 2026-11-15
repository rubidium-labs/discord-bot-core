"""The command tree: error delegation and per-invocation logging."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from discord_bot_core.bot.core_bot import CoreBot  # noqa: F401

logger = logging.getLogger(__name__)


class CoreCommandTree(app_commands.CommandTree["CoreBot"]):
    """The application command tree used by :class:`CoreBot`.

    It adds two behaviours to the discord.py tree: errors are delegated to the
    bot's :class:`~discord_bot_core.errors.ErrorHandler`, and every invocation is
    logged once at INFO with the command name, the user id and the guild id.
    Command options are never logged.

    Example:
        >>> tree = CoreCommandTree(bot)  # doctest: +SKIP
    """

    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError, /
    ) -> None:
        """Delegate a failed command to the bot's error handler.

        Args:
            interaction: The interaction whose command failed.
            error: The app command error raised by discord.py.
        """
        await self.client.error_handler.handle(interaction, error)

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Log the invocation and let it through.

        One INFO line per invocation: the command's qualified name, the user id
        and the guild id (``None`` in DMs). Options are never logged. This check
        always returns ``True`` and never raises; user-visible checks (such as the
        owner check) are command checks, not tree checks.

        Args:
            interaction: The interaction about to be processed.

        Returns:
            Always ``True``.
        """
        command = interaction.command
        name = command.qualified_name if command is not None else "<unknown>"
        logger.info(
            "Invoked /%s user=%s guild=%s",
            name,
            interaction.user.id,
            interaction.guild_id,
        )
        return True

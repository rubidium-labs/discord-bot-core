"""The ``/core`` command group: sync and extension management, owner only.

The ``/core`` group is guild-only and every group runs the
:func:`~discord_bot_core.commands.owner_only` check in its ``interaction_check``,
which discord.py calls for a child command before running it, so non-owners get
:class:`~discord_bot_core.errors.OwnerOnlyError` for every command. Replies are
ephemeral embeds built here with plain :class:`discord.Embed` (there is no UI kit
dependency yet).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_core.commands.checks import owner_only
from discord_bot_core.errors import UserFacingError
from discord_bot_core.settings import Environment

if TYPE_CHECKING:
    from discord_bot_core.bot.core_bot import CoreBot

__all__ = ["CoreCog"]

logger = logging.getLogger(__name__)

MAX_CHOICES = 25
_COLOUR_INFO = discord.Colour.blurple()
_COLOUR_SUCCESS = discord.Colour.green()
_COLOUR_WARNING = discord.Colour.orange()
_DIRTY_HINT = "Command definitions changed; run `/core sync dev`."


class _OwnerOnlyGroup(app_commands.Group):
    """A group whose children are owner-only.

    discord.py calls the direct parent group's ``interaction_check`` before a child
    command runs; running the owner check there raises
    :class:`~discord_bot_core.errors.OwnerOnlyError` for non-owners.
    """

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Run the owner check, raising for non-owners.

        Args:
            interaction: The interaction about to run a child command.

        Returns:
            ``True`` for the owner.

        Raises:
            OwnerOnlyError: If the user is not the bot owner.
        """
        await owner_only()(interaction)
        return True


class _OwnerClient(Protocol):
    """The part of ``interaction.client`` the autocomplete owner check reads."""

    def is_owner(self, user: discord.abc.User, /) -> Any:
        """Return whether ``user`` is the bot owner."""
        ...


def _short_name(full: str) -> str:
    return full.rsplit(".", 1)[-1]


def _names(names: list[str]) -> str:
    if not names:
        return "none"
    return ", ".join(f"`{name}`" for name in names)


class CoreCog(commands.Cog):
    """The core's admin cog: the ``/core`` group.

    Example:
        >>> cog = CoreCog(bot)  # doctest: +SKIP
        >>> guild = discord.Object(id=bot.settings.dev_guild_id)  # doctest: +SKIP
        >>> await bot.add_cog(cog, guild=guild)  # doctest: +SKIP
    """

    def __init__(self, bot: CoreBot) -> None:
        """Create the cog.

        Args:
            bot: The bot the commands act on.
        """
        self.bot = bot

    def _manager(self) -> Any:
        manager = self.bot.extension_manager
        if manager is None:
            raise UserFacingError("No extensions package is configured.")
        return manager

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        client: _OwnerClient = interaction.client  # type: ignore[assignment]
        try:
            return bool(await client.is_owner(interaction.user))
        except Exception:
            logger.warning("Owner check failed in autocomplete", exc_info=True)
            return False

    async def _choices(
        self, interaction: discord.Interaction, current: str, names: list[str]
    ) -> list[app_commands.Choice[str]]:
        if not await self._is_owner(interaction):
            return []
        needle = current.lower()
        return [
            app_commands.Choice(name=_short_name(name), value=name)
            for name in names
            if needle in name.lower()
        ][:MAX_CHOICES]

    async def _unloaded_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            manager = self.bot.extension_manager
            if manager is None:
                return []
            return await self._choices(interaction, current, manager.unloaded())
        except Exception:
            logger.warning("Extension autocomplete failed", exc_info=True)
            return []

    async def _loaded_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            manager = self.bot.extension_manager
            if manager is None:
                return []
            return await self._choices(interaction, current, manager.loaded())
        except Exception:
            logger.warning("Extension autocomplete failed", exc_info=True)
            return []

    def _sync_embed(self, scope: str, commands: list[Any]) -> discord.Embed:
        names = [command.name for command in commands]
        embed = discord.Embed(title="Commands synced", colour=_COLOUR_SUCCESS)
        embed.add_field(name="Scope", value=scope, inline=True)
        embed.add_field(name="Count", value=str(len(names)), inline=True)
        embed.add_field(name="Commands", value=_names(names), inline=False)
        return embed

    core = _OwnerOnlyGroup(
        name="core",
        description="Core administration: command sync and extensions.",
        guild_only=True,
    )

    sync = _OwnerOnlyGroup(
        name="sync",
        description="Publish the application commands.",
        parent=core,
    )

    ext = _OwnerOnlyGroup(
        name="ext",
        description="Load, unload, reload and list the extensions.",
        parent=core,
    )

    @sync.command(name="global", description="Publish the global commands.")
    async def sync_global(self, interaction: discord.Interaction) -> None:
        """Sync the global commands and reply with the count.

        Args:
            interaction: The invoking interaction.
        """
        commands = await self.bot.sync_global()
        embed = self._sync_embed("global", commands)
        if self.bot.settings.environment is Environment.DEV:
            embed.colour = _COLOUR_WARNING
            embed.add_field(
                name="Note",
                value=(
                    "environment is dev; global commands are normally "
                    "not published here."
                ),
                inline=False,
            )
        logger.info(
            "Synced commands scope=global count=%d user=%s",
            len(commands),
            interaction.user.id,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @sync.command(name="dev", description="Sync the dev guild's commands.")
    async def sync_dev(self, interaction: discord.Interaction) -> None:
        """Sync the dev guild: reset, copy and sync in dev; sync only in prod.

        Args:
            interaction: The invoking interaction.
        """
        commands = await self.bot.sync_dev_guild()
        scope = "dev guild (reset, copy, sync)"
        if self.bot.settings.environment is Environment.PROD:
            scope = "dev guild (admin commands only)"
        logger.info(
            "Synced commands scope=dev count=%d user=%s",
            len(commands),
            interaction.user.id,
        )
        await interaction.response.send_message(
            embed=self._sync_embed(scope, commands), ephemeral=True
        )

    @sync.command(name="guild", description="Sync the commands of one guild.")
    @app_commands.describe(guild_id="The guild id to sync to.")
    async def sync_guild(self, interaction: discord.Interaction, guild_id: str) -> None:
        """Sync one guild's commands, parsed from a string id.

        Args:
            interaction: The invoking interaction.
            guild_id: The guild id as a string (Discord integers overflow options).

        Raises:
            UserFacingError: If ``guild_id`` is not a positive integer.
        """
        try:
            parsed = int(guild_id)
        except ValueError as error:
            raise UserFacingError(f"`{guild_id}` is not a valid guild id.") from error
        if parsed <= 0:
            raise UserFacingError(f"`{guild_id}` is not a valid guild id.")
        commands = await self.bot.sync_guild(parsed)
        logger.info(
            "Synced commands scope=guild count=%d user=%s",
            len(commands),
            interaction.user.id,
        )
        await interaction.response.send_message(
            embed=self._sync_embed(f"guild {parsed}", commands), ephemeral=True
        )

    @ext.command(name="load", description="Load an extension.")
    @app_commands.autocomplete(name=_unloaded_autocomplete)
    @app_commands.describe(name="The extension to load.")
    async def ext_load(self, interaction: discord.Interaction, name: str) -> None:
        """Load an extension and tell the owner to sync if the tree is dirty.

        Args:
            interaction: The invoking interaction.
            name: The short or full extension name.
        """
        await self._manager().load(name)
        await self._ext_reply(interaction, "loaded", name)

    @ext.command(name="unload", description="Unload an extension.")
    @app_commands.autocomplete(name=_loaded_autocomplete)
    @app_commands.describe(name="The extension to unload.")
    async def ext_unload(self, interaction: discord.Interaction, name: str) -> None:
        """Unload an extension and tell the owner to sync if the tree is dirty.

        Args:
            interaction: The invoking interaction.
            name: The short or full extension name.
        """
        await self._manager().unload(name)
        await self._ext_reply(interaction, "unloaded", name)

    @ext.command(name="reload", description="Reload an extension.")
    @app_commands.autocomplete(name=_loaded_autocomplete)
    @app_commands.describe(name="The extension to reload.")
    async def ext_reload(self, interaction: discord.Interaction, name: str) -> None:
        """Reload an extension and tell the owner to sync if the tree is dirty.

        Args:
            interaction: The invoking interaction.
            name: The short or full extension name.
        """
        await self._manager().reload(name)
        await self._ext_reply(interaction, "reloaded", name)

    @ext.command(name="list", description="List the extensions and their state.")
    async def ext_list(self, interaction: discord.Interaction) -> None:
        """Reply with the loaded and available extensions.

        Args:
            interaction: The invoking interaction.
        """
        manager = self._manager()
        loaded = manager.loaded()
        unloaded = manager.unloaded()
        embed = discord.Embed(title="Extensions", colour=_COLOUR_INFO)
        embed.add_field(
            name=f"Loaded ({len(loaded)})",
            value=_names([_short_name(name) for name in loaded]),
            inline=False,
        )
        embed.add_field(
            name=f"Available ({len(unloaded)})",
            value=_names([_short_name(name) for name in unloaded]),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _ext_reply(
        self, interaction: discord.Interaction, action: str, name: str
    ) -> None:
        embed = discord.Embed(title=f"Extension {action}", colour=_COLOUR_SUCCESS)
        embed.add_field(name="Extension", value=_short_name(name), inline=True)
        embed.add_field(name="Next", value=_DIRTY_HINT, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

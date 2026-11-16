"""The bot: the composition root's main object and its lifecycle."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_core.bot.tree import CoreCommandTree
from discord_bot_core.commands.admin import CoreCog
from discord_bot_core.errors import ErrorHandler
from discord_bot_core.extensions import ExtensionManager
from discord_bot_core.infrastructure.database import Database
from discord_bot_core.logging_config import configure_logging
from discord_bot_core.settings import CoreSettings, Environment

logger = logging.getLogger(__name__)

_CORE_GROUP_NAME = "core"
"""The name of the core cog's group, kept in the dev guild during a reset."""


class CoreBot(commands.Bot):
    """The base every bot subclasses.

    It wires the settings, the error handler and (optionally) the database, and
    offers logging configuration, cleanup hooks and the command sync helpers. It
    registers no ``on_ready`` handler; the core cog (``/core``) and the extensions
    are added by :meth:`setup_hook`.

    Example:
        >>> settings = CoreSettings(discord_token="x", dev_guild_id=1)  # doctest: +SKIP
        >>> bot = CoreBot(settings)  # doctest: +SKIP
        >>> bot.launch()  # doctest: +SKIP
    """

    def __init__(
        self,
        settings: CoreSettings,
        *,
        extensions_package: str | None = None,
        database: Database | None = None,
        error_handler: ErrorHandler | None = None,
        intents: discord.Intents | None = None,
        **options: Any,
    ) -> None:
        """Create the bot.

        Args:
            settings: The validated settings; the token is read only by
                :meth:`launch`.
            extensions_package: The package the extensions are discovered in;
                when given, an :class:`~discord_bot_core.extensions.ExtensionManager`
                is built for it and :meth:`setup_hook` loads the extensions.
            database: The database, or ``None``; disposed by :meth:`close`.
            error_handler: The error handler; defaults to one built from
                ``settings``.
            intents: The gateway intents; defaults to
                :meth:`discord.Intents.default`, which requests no privileged
                intent.
            **options: Passed through to :class:`discord.ext.commands.Bot`.
        """
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents if intents is not None else discord.Intents.default(),
            tree_cls=CoreCommandTree,
            **options,
        )
        self.settings = settings
        self.database: Database | None = database
        self.error_handler = error_handler or ErrorHandler(settings)
        self.extensions_package = extensions_package
        self.extension_manager: ExtensionManager | None = (
            ExtensionManager(self, extensions_package)
            if extensions_package is not None
            else None
        )
        self._cleanups: list[Callable[[], Awaitable[None]]] = []

    @property
    def tree(self) -> CoreCommandTree:
        """The command tree, a :class:`CoreCommandTree`."""
        tree = super().tree
        assert isinstance(tree, CoreCommandTree)
        return tree

    async def setup_hook(self) -> None:
        """Prepare the bot before the gateway connects.

        Logs whether a database is configured (never its URL), calls
        :meth:`configure`, adds the core cog scoped to the dev guild (so ``/core``
        exists only there) and, when ``extensions_package`` was given, loads the
        extensions. A failing extension is logged with its traceback and the bot
        continues; nothing is synced here.
        """
        if self.database is None:
            logger.info("No database configured")
        else:
            logger.info("Database configured")
        await self.configure()
        await self.add_cog(
            CoreCog(self), guild=discord.Object(id=self.settings.dev_guild_id)
        )
        if self.extension_manager is not None:
            report = await self.extension_manager.load_all()
            for name, message in report.failed.items():
                logger.warning("Extension %s failed to load: %s", name, message)

    async def configure(self) -> None:
        """Application override point, called once from :meth:`setup_hook`.

        The default does nothing; subclasses add their own setup here.
        """

    def register_cleanup(self, fn: Callable[[], Awaitable[None]]) -> None:
        """Register a coroutine function to run on :meth:`close`.

        Args:
            fn: An awaitable callable, called in registration order.
        """
        self._cleanups.append(fn)

    async def sync_global(self) -> list[app_commands.AppCommand]:
        """Publish the global commands.

        Returns:
            The commands Discord reports as synced.
        """
        return await self.tree.sync()

    async def sync_guild(self, guild_id: int) -> list[app_commands.AppCommand]:
        """Sync the guild-scoped commands of one guild.

        Args:
            guild_id: The guild to sync to.

        Returns:
            The commands Discord reports as synced.
        """
        return await self.tree.sync(guild=discord.Object(id=guild_id))

    async def sync_dev_guild(self) -> list[app_commands.AppCommand]:
        """Sync the dev guild's commands.

        In dev: reset, copy and sync. Removes every guild-scoped command from the
        dev guild except the ``/core`` group (``copy_global_to`` never removes
        stale ones), copies the global commands over and syncs. Idempotent, so it
        is safe to run on every ``/core sync dev``.

        In prod: syncs the dev guild only (its admin commands), without copying the
        global commands.

        Returns:
            The commands Discord reports as synced.
        """
        dev = discord.Object(id=self.settings.dev_guild_id)
        if self.settings.environment is Environment.DEV:
            for command in self.tree.get_commands(guild=dev):
                if command.name != _CORE_GROUP_NAME:
                    self.tree.remove_command(command.name, guild=dev)
            self.tree.copy_global_to(guild=dev)
        return await self.tree.sync(guild=dev)

    async def sync_dev_guild_once(self) -> list[app_commands.AppCommand]:
        """Log in without the gateway and sync the dev guild, for bootstrap.

        Call it inside ``async with bot:`` so the login and :meth:`setup_hook`
        run first; the websocket is never opened.

        Returns:
            The commands Discord reports as synced.
        """
        return await self.sync_dev_guild()

    def launch(self) -> None:
        """Configure logging and run the bot with the configured token.

        Passes ``log_handler=None`` so discord.py does not install a second
        handler; the library configures logging once.
        """
        configure_logging(self.settings.log_level, self.settings.environment)
        self.run(self.settings.discord_token.get_secret_value(), log_handler=None)

    async def close(self) -> None:
        """Run the registered cleanups, dispose the database and close."""
        for cleanup in self._cleanups:
            await cleanup()
        if self.database is not None:
            await self.database.dispose()
        await super().close()

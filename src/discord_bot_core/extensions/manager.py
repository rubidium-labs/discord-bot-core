"""The extension manager: load, unload and reload the extensions of a package.

:class:`ExtensionManager` takes any object with the discord.py extension API
(``load_extension``/``unload_extension``/``reload_extension`` coroutines, an
``extensions`` dict and a ``tree``). In production that is ``CoreBot``; in tests it
is a small stub. The manager only manages names inside the package it was given, so
an owner cannot load an arbitrary importable module through the command.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from discord.ext import commands

from discord_bot_core.errors import UserFacingError
from discord_bot_core.extensions.discovery import discover_extensions

if TYPE_CHECKING:
    from discord_bot_core.bot.core_bot import CoreBot

__all__ = ["ExtensionManager", "LoadReport"]

logger = logging.getLogger(__name__)


@dataclass
class LoadReport:
    """The outcome of :meth:`ExtensionManager.load_all`.

    Attributes:
        loaded: The fully-qualified names that loaded successfully.
        failed: The names that failed, mapped to a plain message (no traceback).
    """

    loaded: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class ExtensionManager:
    """Manage the extensions inside a single package.

    Example:
        >>> manager = ExtensionManager(bot, "rubidium_bot.cogs")  # doctest: +SKIP
        >>> await manager.load("secret_santa")  # doctest: +SKIP
    """

    def __init__(self, bot: CoreBot, package: str) -> None:
        """Create the manager.

        Args:
            bot: The bot; any object with the discord.py extension API (in
                production, :class:`~discord_bot_core.bot.core_bot.CoreBot`).
            package: The package that holds the extensions.
        """
        self._bot = bot
        self._package = package

    def available(self) -> list[str]:
        """Return the discovered extensions (fully-qualified, sorted)."""
        return discover_extensions(self._package)

    def loaded(self) -> list[str]:
        """Return the discovered extensions that are currently loaded."""
        return [name for name in self.available() if name in self._bot.extensions]

    def unloaded(self) -> list[str]:
        """Return the discovered extensions that are not loaded."""
        return [name for name in self.available() if name not in self._bot.extensions]

    def resolve(self, short_or_full: str) -> str:
        """Resolve a short or full name to its fully-qualified name.

        Only names inside the configured package are accepted: ``"os"``,
        ``"os.path"`` or any module outside the package is rejected, so the command
        cannot load arbitrary code.

        Args:
            short_or_full: A short name (``"secret_santa"``) or a full name
                (``"rubidium_bot.cogs.secret_santa"``).

        Returns:
            The fully-qualified name.

        Raises:
            UserFacingError: If the name is outside the package or does not name a
                discovered extension.
        """
        if short_or_full == self._package:
            full = self._package
        elif short_or_full.startswith(f"{self._package}."):
            full = short_or_full
        elif "." not in short_or_full:
            full = f"{self._package}.{short_or_full}"
        else:
            raise UserFacingError(f"Unknown extension `{short_or_full}`.")
        if full not in self.available():
            raise UserFacingError(f"Unknown extension `{short_or_full}`.")
        return full

    async def load(self, name: str) -> None:
        """Load an extension.

        Args:
            name: A short or full name; resolved with :meth:`resolve`.

        Raises:
            UserFacingError: If the name is outside the package or loading fails.
        """
        full = self.resolve(name)
        try:
            await self._bot.load_extension(full)
        except commands.errors.ExtensionFailed as error:
            logger.warning("Extension %s failed to load", full, exc_info=error.original)
            raise UserFacingError(self._message(error)) from error
        except commands.errors.ExtensionError as error:
            raise UserFacingError(self._message(error)) from error

    async def unload(self, name: str) -> None:
        """Unload an extension.

        Args:
            name: A short or full name; resolved with :meth:`resolve`.

        Raises:
            UserFacingError: If the name is outside the package or unloading fails.
        """
        full = self.resolve(name)
        try:
            await self._bot.unload_extension(full)
        except commands.errors.ExtensionError as error:
            raise UserFacingError(self._message(error)) from error

    async def reload(self, name: str) -> None:
        """Reload an extension.

        Args:
            name: A short or full name; resolved with :meth:`resolve`.

        Raises:
            UserFacingError: If the name is outside the package or reloading fails.
        """
        full = self.resolve(name)
        try:
            await self._bot.reload_extension(full)
        except commands.errors.ExtensionFailed as error:
            logger.warning(
                "Extension %s failed to reload", full, exc_info=error.original
            )
            raise UserFacingError(self._message(error)) from error
        except commands.errors.ExtensionError as error:
            raise UserFacingError(self._message(error)) from error

    async def load_all(self) -> LoadReport:
        """Load every unloaded extension, continuing after failures.

        Returns:
            The report of what loaded and what failed, with a plain message per
            failure.
        """
        report = LoadReport()
        for name in self.unloaded():
            try:
                await self.load(name)
            except UserFacingError as error:
                report.failed[name] = error.message
            else:
                report.loaded.append(name)
        return report

    def _message(self, error: commands.errors.ExtensionError) -> str:
        name = getattr(error, "name", None) or "<unknown>"
        if isinstance(error, commands.errors.ExtensionAlreadyLoaded):
            return f"Extension `{name}` is already loaded."
        if isinstance(error, commands.errors.ExtensionNotLoaded):
            return f"Extension `{name}` is not loaded."
        if isinstance(error, commands.errors.ExtensionNotFound):
            return f"Extension `{name}` was not found."
        if isinstance(error, commands.errors.NoEntryPointError):
            return f"Extension `{name}` has no `setup` function."
        if isinstance(error, commands.errors.ExtensionFailed):
            return f"Extension `{name}` failed to load."
        return f"Extension `{name}` failed: {error}"

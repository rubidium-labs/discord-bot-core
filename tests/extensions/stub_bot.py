"""A stub bot implementing the discord.py extension API for the manager tests."""

from __future__ import annotations

import importlib
from typing import Any

from discord.ext import commands


class StubBot:
    """A minimal bot mimicking discord.py's load/unload/reload semantics."""

    def __init__(self) -> None:
        self.extensions: dict[str, Any] = {}
        self.tree: Any = object()

    async def load_extension(self, name: str, **kwargs: Any) -> None:
        if name in self.extensions:
            raise commands.errors.ExtensionAlreadyLoaded(name)
        try:
            module = importlib.import_module(name)
        except ImportError as error:
            raise commands.errors.ExtensionNotFound(name) from error
        setup = getattr(module, "setup", None)
        if setup is None:
            raise commands.errors.NoEntryPointError(name)
        try:
            await setup(self)
        except Exception as error:
            raise commands.errors.ExtensionFailed(name, error) from error
        self.extensions[name] = module

    async def unload_extension(self, name: str, **kwargs: Any) -> None:
        if name not in self.extensions:
            raise commands.errors.ExtensionNotLoaded(name)
        module = self.extensions.pop(name)
        teardown = getattr(module, "teardown", None)
        if teardown is not None:
            await teardown(self)

    async def reload_extension(self, name: str, **kwargs: Any) -> None:
        await self.unload_extension(name)
        await self.load_extension(name)

"""Tests for the sync helpers: reset, copy and sync of the dev guild."""

from typing import Any

import discord
from discord import app_commands

from discord_bot_core.bot import CoreBot, CoreCommandTree
from discord_bot_core.settings import CoreSettings

DEV_GUILD_ID = 1


def _settings(environment: str = "dev") -> CoreSettings:
    return CoreSettings(
        discord_token="token",
        dev_guild_id=DEV_GUILD_ID,
        environment=environment,
        _env_file=None,
    )


class SyncSpyTree(CoreCommandTree):
    def __init__(self, client: CoreBot) -> None:
        super().__init__(client)
        self.calls: list[str] = []
        self.synced: list[int | None] = []

    async def sync(self, *, guild: Any = None) -> list[Any]:
        self.calls.append("sync")
        self.synced.append(None if guild is None else guild.id)
        return []

    def remove_command(self, command: str, /, **kwargs: Any) -> Any:
        self.calls.append("remove")
        return super().remove_command(command, **kwargs)

    def copy_global_to(self, *, guild: Any) -> None:
        self.calls.append("copy")
        super().copy_global_to(guild=guild)


def _bot_with_spy(environment: str = "dev") -> tuple[CoreBot, SyncSpyTree]:
    bot = CoreBot(_settings(environment))
    bot._connection._command_tree = None
    tree = SyncSpyTree(bot)
    bot._connection._command_tree = tree
    bot._BotBase__tree = tree
    return bot, tree


async def test_sync_dev_guild_keeps_core_and_removes_stale() -> None:
    bot, tree = _bot_with_spy()

    @app_commands.command(name="stale")
    async def stale(interaction: discord.Interaction) -> None:
        pass

    @app_commands.command(name="core")
    async def core(interaction: discord.Interaction) -> None:
        pass

    dev = discord.Object(id=DEV_GUILD_ID)
    tree.add_command(stale, guild=dev)
    tree.add_command(core, guild=dev)

    await bot.sync_dev_guild()
    names = {command.name for command in tree.get_commands(guild=dev)}
    assert names == {"core"}
    assert "remove" in tree.calls


async def test_sync_dev_guild_reset_copy_sync_order() -> None:
    bot, tree = _bot_with_spy()
    await bot.sync_dev_guild()
    assert tree.calls == ["copy", "sync"]
    assert tree.synced == [DEV_GUILD_ID]


async def test_sync_dev_guild_removes_stale_guild_commands() -> None:
    bot, tree = _bot_with_spy()

    @app_commands.command(name="stale")
    async def stale(interaction: discord.Interaction) -> None:
        pass

    @app_commands.command(name="fresh")
    async def fresh(interaction: discord.Interaction) -> None:
        pass

    dev = discord.Object(id=DEV_GUILD_ID)
    tree.add_command(stale, guild=dev)
    tree.add_command(fresh)

    await bot.sync_dev_guild()
    names = {command.name for command in tree.get_commands(guild=dev)}
    assert names == {"fresh"}


async def test_sync_dev_guild_is_idempotent() -> None:
    bot, tree = _bot_with_spy()

    @app_commands.command(name="fresh")
    async def fresh(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(fresh)
    await bot.sync_dev_guild()
    await bot.sync_dev_guild()
    names = {command.name for command in tree.get_commands(guild=discord.Object(id=1))}
    assert names == {"fresh"}


async def test_sync_dev_guild_keeps_real_core_group() -> None:
    from discord_bot_core.commands.admin import CoreCog

    bot, tree = _bot_with_spy()
    await bot.add_cog(CoreCog(bot), guild=discord.Object(id=DEV_GUILD_ID))

    @app_commands.command(name="stale")
    async def stale(interaction: discord.Interaction) -> None:
        pass

    @app_commands.command(name="fresh")
    async def fresh(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(stale, guild=discord.Object(id=DEV_GUILD_ID))
    tree.add_command(fresh)

    await bot.sync_dev_guild()
    names = {
        command.name
        for command in tree.get_commands(guild=discord.Object(id=DEV_GUILD_ID))
    }
    assert names == {"core", "fresh"}


async def test_sync_dev_guild_prod_does_not_copy() -> None:
    bot, tree = _bot_with_spy(environment="prod")

    @app_commands.command(name="fresh")
    async def fresh(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(fresh)
    await bot.sync_dev_guild()
    assert "copy" not in tree.calls
    assert tree.calls == ["sync"]
    assert tree.synced == [DEV_GUILD_ID]


async def test_sync_global_syncs_without_guild() -> None:
    bot, tree = _bot_with_spy()
    await bot.sync_global()
    assert tree.synced == [None]


async def test_sync_guild_targets_given_guild() -> None:
    bot, tree = _bot_with_spy()
    await bot.sync_guild(99)
    assert tree.synced == [99]


async def test_sync_dev_guild_once_syncs_only_core_no_copy() -> None:
    """Bootstrap syncs the dev guild but never copies global commands over.

    A fresh application must get exactly the ``/core`` group (which loads the
    extensions); cog commands are registered by ``/core ext load`` + a later
    ``/core sync dev``, not by the bootstrap.
    """
    from discord_bot_core.commands.admin import CoreCog

    bot, tree = _bot_with_spy()
    await bot.add_cog(CoreCog(bot), guild=discord.Object(id=DEV_GUILD_ID))

    @app_commands.command(name="cogcmd")
    async def cogcmd(interaction: discord.Interaction) -> None:
        pass

    tree.add_command(cogcmd)  # global command a loaded cog would add

    await bot.sync_dev_guild_once()
    assert tree.calls == ["remove", "sync"] or tree.calls == ["sync"]
    assert "copy" not in tree.calls
    assert tree.synced == [DEV_GUILD_ID]
    names = {
        command.name
        for command in tree.get_commands(guild=discord.Object(id=DEV_GUILD_ID))
    }
    assert names == {"core"}

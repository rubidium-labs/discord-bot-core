"""Tests for the core cog: ``/core sync`` and ``/core ext``."""

from __future__ import annotations

import logging
from typing import Any

import discord
import pytest
from discord import app_commands

from discord_bot_core.bot import CoreBot
from discord_bot_core.commands.admin import CoreCog
from discord_bot_core.errors import OwnerOnlyError, UserFacingError
from discord_bot_core.settings import CoreSettings
from discord_bot_core.testing import FakeClient, FakeInteraction

DEV_GUILD_ID = 42


def _settings(environment: str = "dev") -> CoreSettings:
    return CoreSettings(
        discord_token="token",
        dev_guild_id=DEV_GUILD_ID,
        environment=environment,
        _env_file=None,
    )


class OwnerClient(FakeClient):
    def __init__(self, owner_id: int = 1, **extras: Any) -> None:
        super().__init__(**extras)
        self.owner_id = owner_id

    async def is_owner(self, user: Any, /) -> bool:
        return user.id == self.owner_id


def _interaction(owner: bool = True, **extras: Any) -> FakeInteraction:
    client = OwnerClient(owner_id=1 if owner else 99, **extras)
    return FakeInteraction(client=client)


def _cog(environment: str = "dev", **extras: Any) -> CoreCog:
    bot = CoreBot(_settings(environment), **extras)
    return CoreCog(bot)


async def _add_to_tree(cog: CoreCog) -> CoreBot:
    bot = cog.bot
    await bot.add_cog(cog, guild=discord.Object(id=DEV_GUILD_ID))
    return bot


async def test_core_registered_in_dev_guild_only() -> None:
    cog = _cog()
    bot = await _add_to_tree(cog)
    try:
        dev = discord.Object(id=DEV_GUILD_ID)
        dev_names = {command.name for command in bot.tree.get_commands(guild=dev)}
        global_names = {command.name for command in bot.tree.get_commands()}
        assert "core" in dev_names
        assert "core" not in global_names
    finally:
        await bot.close()


async def test_core_group_is_guild_only_and_owner_checked() -> None:
    cog = _cog()
    bot = await _add_to_tree(cog)
    try:
        core = bot.tree.get_command("core", guild=discord.Object(id=DEV_GUILD_ID))
        assert isinstance(core, app_commands.Group)
        assert core.guild_only is True
    finally:
        await bot.close()


async def test_owner_only_check_raises_for_non_owner() -> None:
    cog = _cog()
    bot = await _add_to_tree(cog)
    try:
        core = bot.tree.get_command("core", guild=discord.Object(id=DEV_GUILD_ID))
        assert isinstance(core, app_commands.Group)
        for group in (core, core._children["sync"], core._children["ext"]):
            with pytest.raises(OwnerOnlyError):
                await group.interaction_check(_interaction(owner=False))
            assert await group.interaction_check(_interaction(owner=True)) is True
    finally:
        await bot.close()


async def test_leaf_command_check_runs_parent_owner_check() -> None:
    cog = _cog()
    bot = await _add_to_tree(cog)
    try:
        core = bot.tree.get_command("core", guild=discord.Object(id=DEV_GUILD_ID))
        assert isinstance(core, app_commands.Group)
        leaf = core._children["sync"]._children["global"]
        with pytest.raises(OwnerOnlyError):
            await leaf._check_can_run(_interaction(owner=False))
        assert await leaf._check_can_run(_interaction(owner=True)) is True
    finally:
        await bot.close()


async def test_sync_global_calls_sync_global_and_replies_ephemeral() -> None:
    cog = _cog(environment="prod")
    calls: list[str] = []

    async def fake_sync_global() -> list[Any]:
        calls.append("global")
        return []

    cog.bot.sync_global = fake_sync_global  # type: ignore[method-assign]
    interaction = _interaction()
    await cog.sync_global.callback(cog, interaction)  # type: ignore[attr-defined]
    assert calls == ["global"]
    sent = interaction.response.sent[0]
    assert sent.ephemeral is True
    assert sent.embed is not None


async def test_sync_global_in_dev_adds_warning() -> None:
    cog = _cog(environment="dev")

    async def fake_sync_global() -> list[Any]:
        return []

    cog.bot.sync_global = fake_sync_global  # type: ignore[method-assign]
    interaction = _interaction()
    await cog.sync_global.callback(cog, interaction)  # type: ignore[attr-defined]
    embed = interaction.response.sent[0].embed
    assert any("dev" in field.value for field in embed.fields)


async def test_sync_dev_calls_sync_dev_guild() -> None:
    cog = _cog()
    calls: list[str] = []

    async def fake_sync_dev_guild() -> list[Any]:
        calls.append("dev")
        return []

    cog.bot.sync_dev_guild = fake_sync_dev_guild  # type: ignore[method-assign]
    interaction = _interaction()
    await cog.sync_dev.callback(cog, interaction)  # type: ignore[attr-defined]
    assert calls == ["dev"]
    assert interaction.response.sent[0].ephemeral is True


async def test_sync_guild_parses_string() -> None:
    cog = _cog()
    synced: list[int] = []

    async def fake_sync_guild(guild_id: int) -> list[Any]:
        synced.append(guild_id)
        return []

    cog.bot.sync_guild = fake_sync_guild  # type: ignore[method-assign]
    interaction = _interaction()
    await cog.sync_guild.callback(cog, interaction, guild_id="123")  # type: ignore[attr-defined]
    assert synced == [123]


@pytest.mark.parametrize("bad", ["abc", "", "-1", "0", "1.5"])
async def test_sync_guild_bad_input_raises_user_facing(bad: str) -> None:
    cog = _cog()
    interaction = _interaction()
    with pytest.raises(UserFacingError):
        await cog.sync_guild.callback(cog, interaction, guild_id=bad)  # type: ignore[attr-defined]


class FakeManager:
    def __init__(
        self,
        loaded: list[str] | None = None,
        unloaded: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._loaded = loaded or []
        self._unloaded = unloaded or []
        self._error = error
        self.calls: list[tuple[str, str]] = []

    def loaded(self) -> list[str]:
        return self._loaded

    def unloaded(self) -> list[str]:
        return self._unloaded

    async def load(self, name: str) -> None:
        self.calls.append(("load", name))
        if self._error is not None:
            raise self._error

    async def unload(self, name: str) -> None:
        self.calls.append(("unload", name))
        if self._error is not None:
            raise self._error

    async def reload(self, name: str) -> None:
        self.calls.append(("reload", name))
        if self._error is not None:
            raise self._error


async def test_ext_load_calls_manager_and_hints_sync() -> None:
    cog = _cog()
    manager = FakeManager()
    cog.bot.extension_manager = manager  # type: ignore[assignment]
    interaction = _interaction()
    await cog.ext_load.callback(cog, interaction, name="good")  # type: ignore[attr-defined]
    assert manager.calls == [("load", "good")]
    embed = interaction.response.sent[0].embed
    assert any("sync dev" in field.value for field in embed.fields)


async def test_ext_unload_and_reload() -> None:
    cog = _cog()
    manager = FakeManager()
    cog.bot.extension_manager = manager  # type: ignore[assignment]
    await cog.ext_unload.callback(cog, _interaction(), name="good")  # type: ignore[attr-defined]
    await cog.ext_reload.callback(cog, _interaction(), name="good")  # type: ignore[attr-defined]
    assert manager.calls == [("unload", "good"), ("reload", "good")]


async def test_ext_command_maps_manager_error() -> None:
    cog = _cog()
    cog.bot.extension_manager = FakeManager(  # type: ignore[assignment]
        error=UserFacingError("Extension `x` is not loaded.")
    )
    with pytest.raises(UserFacingError):
        await cog.ext_load.callback(cog, _interaction(), name="x")  # type: ignore[attr-defined]


async def test_ext_without_manager_raises_user_facing() -> None:
    cog = _cog()
    assert cog.bot.extension_manager is None
    with pytest.raises(UserFacingError):
        await cog.ext_list.callback(cog, _interaction())  # type: ignore[attr-defined]


async def test_ext_list_shows_loaded_and_available() -> None:
    cog = _cog()
    cog.bot.extension_manager = FakeManager(  # type: ignore[assignment]
        loaded=["pkg.good"], unloaded=["pkg.other"]
    )
    interaction = _interaction()
    await cog.ext_list.callback(cog, interaction)  # type: ignore[attr-defined]
    embed = interaction.response.sent[0].embed
    text = " ".join(field.value for field in embed.fields)
    assert "good" in text
    assert "other" in text


async def test_autocomplete_filters_and_limits() -> None:
    cog = _cog()
    names = [f"pkg.ext_{index:02d}" for index in range(40)]
    cog.bot.extension_manager = FakeManager(unloaded=names)  # type: ignore[assignment]
    interaction = _interaction()
    choices = await cog._unloaded_autocomplete(interaction, "")  # type: ignore[arg-type]
    assert len(choices) == 25
    assert choices[0].name == "ext_00"
    assert choices[0].value == "pkg.ext_00"

    filtered = await cog._unloaded_autocomplete(interaction, "ext_1")  # type: ignore[arg-type]
    assert {choice.value for choice in filtered} == {
        f"pkg.ext_{index:02d}" for index in range(10, 20)
    }


async def test_autocomplete_empty_for_non_owner() -> None:
    cog = _cog()
    cog.bot.extension_manager = FakeManager(unloaded=["pkg.good"])  # type: ignore[assignment]
    choices = await cog._unloaded_autocomplete(_interaction(owner=False), "")  # type: ignore[arg-type]
    assert choices == []


async def test_autocomplete_never_raises() -> None:
    cog = _cog()

    class BrokenManager(FakeManager):
        def unloaded(self) -> list[str]:
            raise RuntimeError("boom")

    cog.bot.extension_manager = BrokenManager()  # type: ignore[assignment]
    assert await cog._unloaded_autocomplete(_interaction(), "") == []  # type: ignore[arg-type]


async def test_autocomplete_without_manager_returns_empty() -> None:
    cog = _cog()
    assert cog.bot.extension_manager is None
    assert await cog._loaded_autocomplete(_interaction(), "") == []  # type: ignore[arg-type]


async def test_autocomplete_owner_check_failure_returns_empty() -> None:
    cog = _cog()

    class FailingOwnerClient(FakeClient):
        async def is_owner(self, user: Any, /) -> bool:
            raise RuntimeError("boom")

    cog.bot.extension_manager = FakeManager(unloaded=["pkg.good"])  # type: ignore[assignment]
    interaction = FakeInteraction(client=FailingOwnerClient())
    assert await cog._unloaded_autocomplete(interaction, "") == []  # type: ignore[arg-type]


async def test_setup_hook_adds_core_and_does_not_sync(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = CoreBot(_settings())
    synced: list[Any] = []

    async def fake_sync(*, guild: Any = None) -> list[Any]:
        synced.append(guild)
        return []

    bot.tree.sync = fake_sync  # type: ignore[method-assign]
    try:
        with caplog.at_level(logging.INFO):
            await bot.setup_hook()
        dev = discord.Object(id=DEV_GUILD_ID)
        assert "core" in {command.name for command in bot.tree.get_commands(guild=dev)}
        assert synced == []
    finally:
        await bot.close()


async def test_setup_hook_loads_extensions_when_package_given() -> None:
    from discord_bot_core.extensions import ExtensionManager

    bot = CoreBot(_settings(), extensions_package="tests.extensions.fixture_pkg")
    assert isinstance(bot.extension_manager, ExtensionManager)
    loaded: list[str] = []

    async def fake_load_all() -> Any:
        loaded.append("all")
        from discord_bot_core.extensions import LoadReport

        return LoadReport()

    bot.extension_manager.load_all = fake_load_all  # type: ignore[method-assign]
    try:
        await bot.setup_hook()
        assert loaded == ["all"]
    finally:
        await bot.close()


async def test_setup_hook_continues_after_failing_extension(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from discord_bot_core.extensions import ExtensionManager

    bot = CoreBot(_settings(), extensions_package="tests.extensions.fixture_pkg")
    assert isinstance(bot.extension_manager, ExtensionManager)
    try:
        with caplog.at_level(logging.WARNING):
            await bot.setup_hook()
        assert "failed" in caplog.text.lower()
        dev = discord.Object(id=DEV_GUILD_ID)
        assert "core" in {command.name for command in bot.tree.get_commands(guild=dev)}
    finally:
        await bot.close()


async def test_sync_commands_wired_to_tree_methods() -> None:
    cog = _cog()
    bot = await _add_to_tree(cog)
    try:
        synced: list[int | None] = []

        async def fake_sync(*, guild: Any = None) -> list[Any]:
            synced.append(None if guild is None else guild.id)
            return []

        bot.tree.sync = fake_sync  # type: ignore[method-assign]
        await cog.sync_global.callback(cog, _interaction())  # type: ignore[attr-defined]
        await cog.sync_guild.callback(cog, _interaction(), guild_id="7")  # type: ignore[attr-defined]
        assert synced == [None, 7]
    finally:
        await bot.close()


def test_subcommands_present() -> None:
    core = CoreCog.core
    assert set(core._children) == {"sync", "ext"}
    assert set(core._children["sync"]._children) == {"global", "dev", "guild"}
    assert set(core._children["ext"]._children) == {"load", "unload", "reload", "list"}

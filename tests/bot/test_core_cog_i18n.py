"""Catalog coverage and runtime translation for the admin cog's strings."""

from __future__ import annotations

from typing import Any

import discord
import pytest

from discord_bot_core.bot import CoreBot
from discord_bot_core.commands.admin import CoreCog
from discord_bot_core.errors import UserFacingError
from discord_bot_core.i18n import CORE_CATALOG
from discord_bot_core.settings import CoreSettings
from discord_bot_core.testing import FakeClient, FakeInteraction

DEV_GUILD_ID = 42


def _settings() -> CoreSettings:
    return CoreSettings(
        discord_token="token",
        dev_guild_id=DEV_GUILD_ID,
        _env_file=None,
    )


class OwnerClient(FakeClient):
    async def is_owner(self, user: Any, /) -> bool:
        return True


class FrenchInteraction(FakeInteraction):
    """A fake interaction whose ``translate`` returns the French catalog text."""

    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return CORE_CATALOG.get(string.message, discord.Locale.french)


def _iter_app_commands(cog: CoreCog) -> list[Any]:
    commands: list[Any] = [CoreCog.core, CoreCog.sync, CoreCog.ext]
    for group in (CoreCog.core, CoreCog.sync, CoreCog.ext):
        commands.extend(group.commands)
    commands.extend(
        [
            cog.sync_global,  # type: ignore[attr-defined]
            cog.sync_dev,  # type: ignore[attr-defined]
            cog.sync_guild,  # type: ignore[attr-defined]
            cog.ext_load,  # type: ignore[attr-defined]
            cog.ext_unload,  # type: ignore[attr-defined]
            cog.ext_reload,  # type: ignore[attr-defined]
            cog.ext_list,  # type: ignore[attr-defined]
        ]
    )
    return commands


def _locale_messages(command: Any) -> list[str]:
    messages: list[str] = []
    locale_description = getattr(command, "_locale_description", None)
    if locale_description is not None:
        messages.append(locale_description.message)
    for parameter in getattr(command, "parameters", ()):
        locale_parameter = getattr(parameter, "locale_description", None)
        if locale_parameter is not None:
            messages.append(locale_parameter.message)
    return messages


def _assert_covered(key: str) -> None:
    assert CORE_CATALOG.get(key, discord.Locale.american_english) is not None, key
    assert CORE_CATALOG.get(key, discord.Locale.french) is not None, key


def test_every_admin_description_key_is_in_the_catalog() -> None:
    cog = CoreCog(CoreBot(_settings()))
    keys = {
        key for command in _iter_app_commands(cog) for key in _locale_messages(command)
    }
    assert keys, "the admin cog must carry locale_str descriptions"
    assert "core.sync.guild.guild_id" in keys
    for key in keys:
        _assert_covered(key)


def test_core_catalog_has_both_locales() -> None:
    locales = CORE_CATALOG.locales()
    assert discord.Locale.american_english in locales
    assert discord.Locale.french in locales


async def test_sync_global_reply_is_french_for_french_user() -> None:
    bot = CoreBot(_settings())

    async def fake_sync_global() -> list[Any]:
        return []

    bot.sync_global = fake_sync_global  # type: ignore[method-assign]
    cog = CoreCog(bot)
    interaction = FrenchInteraction(client=OwnerClient())
    try:
        await cog.sync_global.callback(cog, interaction)  # type: ignore[attr-defined]
        embed = interaction.response.sent[0].embed
        assert embed.title == "Commandes synchronisées"
        assert [field.name for field in embed.fields] == [
            "Portée",
            "Nombre",
            "Commandes",
        ]
    finally:
        await bot.close()


async def test_ext_list_reply_is_french_for_french_user() -> None:
    cog = CoreCog(CoreBot(_settings()))
    cog.bot.extension_manager = _Manager(loaded=["pkg.good"], unloaded=[])  # type: ignore[assignment]
    interaction = FrenchInteraction(client=OwnerClient())
    await cog.ext_list.callback(cog, interaction)  # type: ignore[attr-defined]
    embed = interaction.response.sent[0].embed
    assert embed.title == "Extensions"
    assert embed.fields[0].name == "Chargées (1)"
    assert embed.fields[1].name == "Disponibles (0)"
    assert embed.fields[1].value == "aucune"


async def test_ext_load_reply_is_french_for_french_user() -> None:
    cog = CoreCog(CoreBot(_settings()))
    cog.bot.extension_manager = _Manager()  # type: ignore[assignment]
    interaction = FrenchInteraction(client=OwnerClient())
    await cog.ext_load.callback(cog, interaction, name="pkg.good")  # type: ignore[attr-defined]
    embed = interaction.response.sent[0].embed
    assert embed.title == "Extension chargée"
    assert any("sync dev" in field.value for field in embed.fields)


async def test_sync_guild_bad_input_uses_english_default() -> None:
    cog = CoreCog(CoreBot(_settings()))
    interaction = FakeInteraction(client=OwnerClient())
    with pytest.raises(UserFacingError) as caught:
        await cog.sync_guild.callback(cog, interaction, guild_id="x")  # type: ignore[attr-defined]
    assert caught.value.message == "`x` is not a valid guild id."


class _Manager:
    def __init__(
        self, loaded: list[str] | None = None, unloaded: list[str] | None = None
    ) -> None:
        self._loaded = loaded or []
        self._unloaded = unloaded or []

    def loaded(self) -> list[str]:
        return self._loaded

    def unloaded(self) -> list[str]:
        return self._unloaded

    async def load(self, name: str) -> None:
        pass

    async def unload(self, name: str) -> None:
        pass

    async def reload(self, name: str) -> None:
        pass

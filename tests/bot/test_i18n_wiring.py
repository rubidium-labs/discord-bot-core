"""Tests for the i18n wiring in :class:`CoreBot`."""

from __future__ import annotations

from typing import Any

import discord
from discord import app_commands

from discord_bot_core.bot import CoreBot
from discord_bot_core.i18n import CORE_CATALOG, CoreTranslator
from discord_bot_core.settings import CoreSettings


def _settings(**overrides: Any) -> CoreSettings:
    values: dict[str, Any] = {
        "discord_token": "token",
        "dev_guild_id": 1,
        "_env_file": None,
    }
    values.update(overrides)
    return CoreSettings(**values)


def test_default_translator_uses_core_catalog_and_settings_locale() -> None:
    bot = CoreBot(_settings(default_locale="fr"))
    assert isinstance(bot.translator, CoreTranslator)
    assert bot.translator.default_locale is discord.Locale.french
    assert bot.translator.catalogs == [CORE_CATALOG]


def test_given_translator_is_used() -> None:
    translator = CoreTranslator()
    bot = CoreBot(_settings(), translator=translator)
    assert bot.translator is translator


async def test_setup_hook_sets_translator_on_tree() -> None:
    bot = CoreBot(_settings())
    seen: list[app_commands.Translator | None] = []

    async def fake_set_translator(translator: app_commands.Translator | None) -> None:
        seen.append(translator)

    bot.tree.set_translator = fake_set_translator  # type: ignore[method-assign]
    try:
        await bot.setup_hook()
        assert seen == [bot.translator]
    finally:
        await bot.close()


async def test_core_sync_reply_is_translated() -> None:
    from discord_bot_core.commands.admin import CoreCog
    from discord_bot_core.testing import FakeClient, FakeInteraction

    bot = CoreBot(_settings())

    async def fake_sync_global() -> list[Any]:
        return []

    bot.sync_global = fake_sync_global  # type: ignore[method-assign]

    class OwnerClient(FakeClient):
        async def is_owner(self, user: Any, /) -> bool:
            return True

    class TranslatingInteraction(FakeInteraction):
        async def translate(self, string: Any, **kwargs: Any) -> str | None:
            return await bot.translator.translate(string, discord.Locale.french, None)

    cog = CoreCog(bot)
    interaction = TranslatingInteraction(client=OwnerClient())
    try:
        await cog.sync_global.callback(cog, interaction)  # type: ignore[attr-defined]
        embed = interaction.response.sent[0].embed
        assert embed.title == "Commandes synchronisées"
    finally:
        await bot.close()


async def test_setup_hook_registers_translator_catalogs_for_runtime() -> None:
    from discord_bot_core.i18n import (
        CORE_CATALOG,
        TranslationCatalog,
        default_text,
        runtime,
    )

    app_catalog = TranslationCatalog()
    app_catalog.register("secret_santa.start", {"en-US": "Secret Santa starts!"})
    bot = CoreBot(
        _settings(),
        translator=CoreTranslator([CORE_CATALOG, app_catalog]),
    )
    try:
        await bot.setup_hook()
        assert default_text("secret_santa.start") == "Secret Santa starts!"
    finally:
        runtime.use_catalogs([CORE_CATALOG])
        await bot.close()

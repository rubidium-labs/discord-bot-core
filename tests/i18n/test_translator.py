"""Tests for :class:`discord_bot_core.i18n.CoreTranslator`."""

from typing import Any

import discord
from discord import app_commands

from discord_bot_core.i18n import CoreTranslator, TranslationCatalog


def _catalog() -> TranslationCatalog:
    catalog = TranslationCatalog()
    catalog.register(
        "core.sync.done", {"en-US": "Commands synced", "fr": "Commandes synchronisées"}
    )
    return catalog


def _context() -> Any:
    return None


async def test_translate_french() -> None:
    translator = CoreTranslator([_catalog()])
    result = await translator.translate(
        app_commands.locale_str("core.sync.done"), discord.Locale.french, _context()
    )
    assert result == "Commandes synchronisées"


async def test_translate_american_english() -> None:
    translator = CoreTranslator([_catalog()])
    result = await translator.translate(
        app_commands.locale_str("core.sync.done"),
        discord.Locale.american_english,
        _context(),
    )
    assert result == "Commands synced"


async def test_translate_falls_back_to_default_locale() -> None:
    translator = CoreTranslator([_catalog()])
    result = await translator.translate(
        app_commands.locale_str("core.sync.done"), discord.Locale.german, _context()
    )
    assert result == "Commands synced"


async def test_translate_returns_none_for_unknown_key() -> None:
    translator = CoreTranslator([_catalog()])
    result = await translator.translate(
        app_commands.locale_str("unknown"), discord.Locale.french, _context()
    )
    assert result is None


async def test_translate_returns_none_when_no_catalogs() -> None:
    translator = CoreTranslator()
    result = await translator.translate(
        app_commands.locale_str("core.sync.done"), discord.Locale.french, _context()
    )
    assert result is None


async def test_translate_searches_catalogs_in_order() -> None:
    first = TranslationCatalog()
    first.register("greet", {"fr": "Premier"})
    second = TranslationCatalog()
    second.register("greet", {"fr": "Second", "en-US": "Second"})
    translator = CoreTranslator([first, second])
    result = await translator.translate(
        app_commands.locale_str("greet"), discord.Locale.french, _context()
    )
    assert result == "Premier"


def test_supported_locales_derived_from_catalogs() -> None:
    translator = CoreTranslator([_catalog()])
    assert translator.supported_locales == frozenset(
        {discord.Locale.american_english, discord.Locale.french}
    )


def test_supported_locales_includes_default() -> None:
    translator = CoreTranslator([], default_locale=discord.Locale.german)
    assert translator.supported_locales == frozenset({discord.Locale.german})


async def test_load_and_unload_are_noops() -> None:
    translator = CoreTranslator([_catalog()])
    assert await translator.load() is None
    assert await translator.unload() is None

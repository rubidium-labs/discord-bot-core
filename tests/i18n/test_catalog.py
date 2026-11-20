"""Tests for :class:`discord_bot_core.i18n.TranslationCatalog`."""

import discord
import pytest

from discord_bot_core.i18n import CORE_CATALOG, TranslationCatalog


def test_get_returns_exact_locale() -> None:
    catalog = TranslationCatalog()
    catalog.register("greet", {"en-US": "Hello", "fr": "Bonjour"})
    assert catalog.get("greet", discord.Locale.french) == "Bonjour"
    assert catalog.get("greet", discord.Locale.american_english) == "Hello"


def test_get_returns_none_for_missing_locale() -> None:
    catalog = TranslationCatalog()
    catalog.register("greet", {"en-US": "Hello"})
    assert catalog.get("greet", discord.Locale.german) is None


def test_get_returns_none_for_unknown_key() -> None:
    catalog = TranslationCatalog()
    assert catalog.get("missing", discord.Locale.french) is None


def test_register_replaces_previous_entry() -> None:
    catalog = TranslationCatalog()
    catalog.register("greet", {"en-US": "Hello"})
    catalog.register("greet", {"en-US": "Hi", "fr": "Salut"})
    assert catalog.get("greet", discord.Locale.american_english) == "Hi"
    assert catalog.get("greet", discord.Locale.french) == "Salut"


def test_register_rejects_empty_translations() -> None:
    catalog = TranslationCatalog()
    with pytest.raises(ValueError):
        catalog.register("greet", {})


def test_locales_returns_every_present_locale() -> None:
    catalog = TranslationCatalog()
    catalog.register("a", {"en-US": "A", "fr": "A"})
    catalog.register("b", {"fr": "B"})
    assert catalog.locales() == frozenset(
        {discord.Locale.american_english, discord.Locale.french}
    )


def test_core_catalog_has_the_sync_message() -> None:
    result = CORE_CATALOG.get("core.sync.done", discord.Locale.american_english)
    assert result is not None

"""Tests for the runtime translation helper (:mod:`discord_bot_core.i18n.runtime`)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import discord
import pytest

from discord_bot_core.i18n import (
    CORE_CATALOG,
    TranslationCatalog,
    default_text,
    translate,
    use_catalogs,
)
from discord_bot_core.testing import FakeInteraction


@pytest.fixture(autouse=True)
def _reset_runtime_catalogs() -> Iterator[None]:
    use_catalogs([CORE_CATALOG])
    yield
    use_catalogs([CORE_CATALOG])


def _app_catalog() -> TranslationCatalog:
    catalog = TranslationCatalog()
    catalog.register(
        "secret_santa.start", {"en-US": "Secret Santa starts!", "fr": "Secret Santa !"}
    )
    return catalog


class FrenchAppInteraction(FakeInteraction):
    def __init__(self, catalog: TranslationCatalog) -> None:
        super().__init__()
        self._catalog = catalog

    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return self._catalog.get(string.message, discord.Locale.french)


class FrenchInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return CORE_CATALOG.get(string.message, discord.Locale.french)


class NoneInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return None


class RawKeyInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return string.message


class LocaleStrInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> Any:
        return string


class BadFormatInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return "Identifiant : {missing}"


def test_default_text_reads_en_us() -> None:
    assert default_text("core.sync.done") == "Commands synced"


def test_default_text_raises_for_unknown_key() -> None:
    with pytest.raises(KeyError):
        default_text("core.missing")


def test_use_catalogs_resolves_app_key_default_text() -> None:
    catalog = _app_catalog()
    use_catalogs([CORE_CATALOG, catalog])
    assert default_text("secret_santa.start") == "Secret Santa starts!"
    assert default_text("core.sync.done") == "Commands synced"


async def test_use_catalogs_resolves_app_key_translate() -> None:
    catalog = _app_catalog()
    use_catalogs([CORE_CATALOG, catalog])
    assert (
        await translate(FakeInteraction(), "secret_santa.start")
        == "Secret Santa starts!"
    )
    assert (
        await translate(FrenchAppInteraction(catalog), "secret_santa.start")
        == "Secret Santa !"
    )


def test_use_catalogs_restores_core_only_behaviour() -> None:
    use_catalogs([CORE_CATALOG, _app_catalog()])
    use_catalogs([CORE_CATALOG])
    with pytest.raises(KeyError):
        default_text("secret_santa.start")


async def test_translate_without_translate_falls_back_to_english() -> None:
    assert await translate(FakeInteraction(), "core.sync.done") == "Commands synced"


async def test_translate_uses_french_when_available() -> None:
    interaction = FrenchInteraction()
    assert await translate(interaction, "core.sync.done") == "Commandes synchronisées"


async def test_translate_none_falls_back_to_english() -> None:
    assert await translate(NoneInteraction(), "core.sync.done") == "Commands synced"


async def test_translate_raw_key_falls_back_to_english() -> None:
    assert await translate(RawKeyInteraction(), "core.sync.done") == "Commands synced"


async def test_translate_raw_key_with_placeholder_uses_english_default() -> None:
    text = await translate(RawKeyInteraction(), "core.sync.guild.invalid", guild_id="x")
    assert text == "`x` is not a valid guild id."


async def test_translate_locale_str_echo_falls_back_to_english() -> None:
    assert (
        await translate(LocaleStrInteraction(), "core.sync.done") == "Commands synced"
    )


async def test_translate_format_key_error_returns_unformatted_text() -> None:
    text = await translate(BadFormatInteraction(), "core.sync.done")
    assert text == "Identifiant : {missing}"


async def test_translate_formats_placeholders() -> None:
    interaction = FrenchInteraction()
    text = await translate(interaction, "errors.generic", error_id="ab12cd34")
    assert "ab12cd34" in text
    assert "{error_id}" not in text

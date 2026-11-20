"""Tests for the runtime translation helper (:mod:`discord_bot_core.i18n.runtime`)."""

from __future__ import annotations

from typing import Any

import discord
import pytest

from discord_bot_core.i18n import CORE_CATALOG, default_text, translate
from discord_bot_core.testing import FakeInteraction


class FrenchInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return CORE_CATALOG.get(string.message, discord.Locale.french)


class NoneInteraction(FakeInteraction):
    async def translate(self, string: Any, **kwargs: Any) -> str | None:
        return None


def test_default_text_reads_en_us() -> None:
    assert default_text("core.sync.done") == "Commands synced"


def test_default_text_raises_for_unknown_key() -> None:
    with pytest.raises(KeyError):
        default_text("core.missing")


async def test_translate_without_translate_falls_back_to_english() -> None:
    assert await translate(FakeInteraction(), "core.sync.done") == "Commands synced"


async def test_translate_uses_french_when_available() -> None:
    interaction = FrenchInteraction()
    assert await translate(interaction, "core.sync.done") == "Commandes synchronisées"


async def test_translate_none_falls_back_to_english() -> None:
    assert await translate(NoneInteraction(), "core.sync.done") == "Commands synced"


async def test_translate_formats_placeholders() -> None:
    interaction = FrenchInteraction()
    text = await translate(interaction, "errors.generic", error_id="ab12cd34")
    assert "ab12cd34" in text
    assert "{error_id}" not in text

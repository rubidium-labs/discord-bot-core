"""Tests for the embed helpers."""

import discord

from discord_bot_core.ui.embeds import (
    DESCRIPTION_LIMIT,
    FIELD_NAME_LIMIT,
    FIELD_VALUE_LIMIT,
    MAX_FIELDS,
    TITLE_LIMIT,
    EmbedField,
    error_embed,
    info_embed,
    success_embed,
    truncate,
    warning_embed,
)
from discord_bot_core.ui.theme import DEFAULT_THEME, EmbedTheme


def test_truncate_keeps_short_text() -> None:
    assert truncate("hello", 10) == "hello"


def test_truncate_adds_ellipsis_and_respects_limit() -> None:
    result = truncate("abcdefghij", 5)
    assert result == "abcd…"
    assert len(result) == 5


def test_truncate_zero_limit() -> None:
    assert truncate("abc", 0) == ""


def test_info_embed_colour_and_footer() -> None:
    theme = EmbedTheme(
        info=discord.Colour.blue(),
        success=discord.Colour.green(),
        warning=discord.Colour.orange(),
        error=discord.Colour.red(),
        footer="Footer",
    )
    embed = info_embed("Title", "Description", theme=theme)
    assert embed.colour == discord.Colour.blue()
    assert embed.title == "Title"
    assert embed.description == "Description"
    assert embed.footer.text == "Footer"


def test_default_theme_has_no_footer() -> None:
    embed = success_embed("Title")
    assert embed.colour == DEFAULT_THEME.success
    assert embed.footer.text is None


def test_each_helper_uses_its_colour() -> None:
    assert info_embed("t").colour == DEFAULT_THEME.info
    assert success_embed("t").colour == DEFAULT_THEME.success
    assert warning_embed("t").colour == DEFAULT_THEME.warning
    assert error_embed("t").colour == DEFAULT_THEME.error


def test_fields_are_added() -> None:
    embed = info_embed("t", fields=[EmbedField("Name", "Value", True)])
    assert embed.fields[0].name == "Name"
    assert embed.fields[0].value == "Value"
    assert embed.fields[0].inline is True


def test_long_title_and_description_truncated() -> None:
    embed = info_embed("t" * 500, "d" * 5000)
    assert embed.title is not None
    assert embed.description is not None
    assert len(embed.title) <= TITLE_LIMIT
    assert len(embed.description) <= DESCRIPTION_LIMIT


def test_long_field_name_and_value_truncated() -> None:
    embed = info_embed("t", fields=[EmbedField("n" * 500, "v" * 2000, False)])
    field = embed.fields[0]
    assert len(field.name) <= FIELD_NAME_LIMIT
    assert len(field.value) <= FIELD_VALUE_LIMIT


def test_more_than_25_fields_dropped() -> None:
    fields = [EmbedField(f"f{i}", "v") for i in range(30)]
    embed = info_embed("t", fields=fields)
    assert len(embed.fields) == MAX_FIELDS

"""Embed helpers that respect Discord's limits.

Each helper builds a ``discord.Embed`` with the theme's colour and footer and
truncates the title, description and fields so a long participant list cannot make
the API call fail.

Example:
    >>> embed = success_embed(  # doctest: +SKIP
    ...     "Done",
    ...     "All messages were delivered.",
    ...     fields=[EmbedField("Delivered", "10", True)],
    ... )
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

import discord

from discord_bot_core.ui.theme import DEFAULT_THEME, EmbedTheme

TITLE_LIMIT = 256
DESCRIPTION_LIMIT = 4096
FIELD_NAME_LIMIT = 256
FIELD_VALUE_LIMIT = 1024
MAX_FIELDS = 25

ELLIPSIS = "…"

__all__ = [
    "DESCRIPTION_LIMIT",
    "ELLIPSIS",
    "FIELD_NAME_LIMIT",
    "FIELD_VALUE_LIMIT",
    "MAX_FIELDS",
    "TITLE_LIMIT",
    "EmbedField",
    "error_embed",
    "info_embed",
    "success_embed",
    "truncate",
    "warning_embed",
]


class EmbedField(NamedTuple):
    """A single embed field.

    Attributes:
        name: The field name.
        value: The field value.
        inline: Whether the field is shown inline with its neighbours.
    """

    name: str
    value: str
    inline: bool = True


def truncate(text: str, limit: int) -> str:
    """Shorten ``text`` to at most ``limit`` characters, ending with an ellipsis.

    When the text fits it is returned unchanged. Otherwise it is cut so the result
    (including the trailing ``…``) never exceeds ``limit``.

    Args:
        text: The text to shorten.
        limit: The maximum length of the result.

    Returns:
        The original text, or a truncated copy ending with ``…``.
    """
    if len(text) <= limit:
        return text
    if limit <= 0:
        return ""
    return text[: limit - 1] + ELLIPSIS


def _build(
    colour: discord.Colour,
    title: str,
    description: str | None,
    fields: Sequence[EmbedField],
    theme: EmbedTheme,
) -> discord.Embed:
    embed = discord.Embed(
        title=truncate(title, TITLE_LIMIT),
        description=truncate(description, DESCRIPTION_LIMIT)
        if description is not None
        else None,
        colour=colour,
    )
    for field in fields[:MAX_FIELDS]:
        embed.add_field(
            name=truncate(field.name, FIELD_NAME_LIMIT),
            value=truncate(field.value, FIELD_VALUE_LIMIT),
            inline=field.inline,
        )
    if theme.footer is not None:
        embed.set_footer(text=theme.footer)
    return embed


def info_embed(
    title: str,
    description: str | None = None,
    *,
    fields: Sequence[EmbedField] = (),
    theme: EmbedTheme = DEFAULT_THEME,
) -> discord.Embed:
    """Build an informational embed.

    Args:
        title: The embed title; truncated to 256 characters.
        description: The embed description; truncated to 4096 characters.
        fields: The fields; at most 25 are kept, each truncated to Discord's limits.
        theme: The theme providing the colour and footer.

    Returns:
        The embed.
    """
    return _build(theme.info, title, description, fields, theme)


def success_embed(
    title: str,
    description: str | None = None,
    *,
    fields: Sequence[EmbedField] = (),
    theme: EmbedTheme = DEFAULT_THEME,
) -> discord.Embed:
    """Build a success embed.

    Args:
        title: The embed title; truncated to 256 characters.
        description: The embed description; truncated to 4096 characters.
        fields: The fields; at most 25 are kept, each truncated to Discord's limits.
        theme: The theme providing the colour and footer.

    Returns:
        The embed.
    """
    return _build(theme.success, title, description, fields, theme)


def warning_embed(
    title: str,
    description: str | None = None,
    *,
    fields: Sequence[EmbedField] = (),
    theme: EmbedTheme = DEFAULT_THEME,
) -> discord.Embed:
    """Build a warning embed.

    Args:
        title: The embed title; truncated to 256 characters.
        description: The embed description; truncated to 4096 characters.
        fields: The fields; at most 25 are kept, each truncated to Discord's limits.
        theme: The theme providing the colour and footer.

    Returns:
        The embed.
    """
    return _build(theme.warning, title, description, fields, theme)


def error_embed(
    title: str,
    description: str | None = None,
    *,
    fields: Sequence[EmbedField] = (),
    theme: EmbedTheme = DEFAULT_THEME,
) -> discord.Embed:
    """Build an error embed.

    Args:
        title: The embed title; truncated to 256 characters.
        description: The embed description; truncated to 4096 characters.
        fields: The fields; at most 25 are kept, each truncated to Discord's limits.
        theme: The theme providing the colour and footer.

    Returns:
        The embed.
    """
    return _build(theme.error, title, description, fields, theme)

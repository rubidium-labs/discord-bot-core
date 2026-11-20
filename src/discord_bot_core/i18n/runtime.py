"""Helpers to translate runtime strings, the ones sent as replies or embeds.

Descriptions are translated once, at sync time, by :class:`CoreTranslator` through
``locale_str``. Replies are translated at runtime, per invoking user, through
``interaction.translate``. :func:`translate` wraps that call and falls back to the
``en-US`` catalog text when the interaction has no translator (a fake in tests) or
returns nothing.
"""

from __future__ import annotations

from typing import Any

import discord
from discord import app_commands

from discord_bot_core.i18n.core_catalog import CORE_CATALOG

__all__ = ["default_text", "translate"]


def default_text(key: str) -> str:
    """Return the ``en-US`` text of ``key``, the fallback when nothing translates it.

    Args:
        key: The symbolic message key.

    Returns:
        The English text.

    Raises:
        KeyError: If the catalog has no ``en-US`` entry for ``key``.
    """
    text = CORE_CATALOG.get(key, discord.Locale.american_english)
    if text is None:
        raise KeyError(f"CORE_CATALOG has no en-US entry for {key!r}")
    return text


async def translate(interaction: Any, key: str, /, **format_args: Any) -> str:
    """Translate ``key`` for the invoking user's locale, formatting its placeholders.

    Uses ``interaction.translate`` when the interaction has it; a fake without one
    gets the ``en-US`` default. A ``None`` from the translator also falls back to the
    default. The result is passed through ``str.format(**format_args)``.

    Args:
        interaction: The invoking interaction.
        key: The symbolic message key.
        **format_args: Values for the ``{placeholder}`` fields of the text.

    Returns:
        The translated, formatted text.
    """
    translate_method = getattr(interaction, "translate", None)
    text: str | None = None
    if translate_method is not None:
        text = await translate_method(app_commands.locale_str(key))
    if text is None:
        text = default_text(key)
    return text.format(**format_args)

"""Helpers to translate runtime strings, the ones sent as replies or embeds.

Descriptions are translated once, at sync time, by :class:`CoreTranslator` through
``locale_str``. Replies are translated at runtime, per invoking user, through
``interaction.translate``. :func:`translate` wraps that call and falls back to the
``en-US`` catalog text when the interaction has no translator (a fake in tests) or
returns nothing.

The fallback resolves the key against the bot's own catalogs (core *and*
application ones), not only ``CORE_CATALOG``: :class:`~discord_bot_core.bot.CoreBot`
calls :func:`use_catalogs` in ``setup_hook`` with its translator's catalogs. Until
then, :data:`_RUNTIME_CATALOGS` holds only ``CORE_CATALOG``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import discord
from discord import app_commands

from discord_bot_core.i18n.catalog import TranslationCatalog
from discord_bot_core.i18n.core_catalog import CORE_CATALOG

__all__ = ["default_text", "translate", "use_catalogs"]

_RUNTIME_CATALOGS: list[TranslationCatalog] = [CORE_CATALOG]
"""The catalogs the runtime fallback searches; set by :func:`use_catalogs`."""


def use_catalogs(catalogs: Sequence[TranslationCatalog]) -> None:
    """Set the catalogs the runtime helpers search, in order.

    Internal-ish: :class:`~discord_bot_core.bot.CoreBot` calls it in
    ``setup_hook`` with the bot's translator catalogs, so application keys resolve
    there without touching ``CORE_CATALOG``. Tests may call it to isolate state
    (``use_catalogs([CORE_CATALOG])`` restores core-only behaviour).

    Args:
        catalogs: The catalogs to search, in order; an empty list falls back to
            ``[CORE_CATALOG]`` so the helpers always have somewhere to look.
    """
    _RUNTIME_CATALOGS[:] = list(catalogs) or [CORE_CATALOG]


def default_text(key: str) -> str:
    """Return the ``en-US`` text of ``key``, the fallback when nothing translates it.

    Searches the runtime catalogs (see :func:`use_catalogs`) in order.

    Args:
        key: The symbolic message key.

    Returns:
        The English text.

    Raises:
        KeyError: If no catalog has an ``en-US`` entry for ``key``.
    """
    for catalog in _RUNTIME_CATALOGS:
        text = catalog.get(key, discord.Locale.american_english)
        if text is not None:
            return text
    raise KeyError(f"No runtime catalog has an en-US entry for {key!r}")


def _format(text: str, format_args: dict[str, Any]) -> str:
    """Fill ``text``'s placeholders, returning it unchanged if the args do not match."""
    try:
        return text.format(**format_args)
    except KeyError, IndexError, ValueError:
        return text


async def translate(interaction: Any, key: str, /, **format_args: Any) -> str:
    """Translate ``key`` for the invoking user's locale, formatting its placeholders.

    Uses ``interaction.translate`` when the interaction has it; a fake without one
    gets the ``en-US`` default. The translator's result counts as untranslated — and
    falls back to ``default_text(key)`` — when it is ``None`` or still equal to the
    key, the ``locale_str`` or its message (a translator that echoes its input). The
    result is passed through ``str.format(**format_args)``; a mismatch between the
    text's placeholders and ``format_args`` returns the unformatted text instead of
    raising.

    Args:
        interaction: The invoking interaction.
        key: The symbolic message key.
        **format_args: Values for the ``{placeholder}`` fields of the text.

    Returns:
        The translated, formatted text.
    """
    locale_string = app_commands.locale_str(key)
    default = default_text(key)
    translate_method = getattr(interaction, "translate", None)
    text: str | None = None
    if translate_method is not None:
        text = await translate_method(locale_string)
    if (
        text is None
        or text == key
        or text == locale_string
        or text == locale_string.message
    ):
        text = default
    return _format(text, format_args)

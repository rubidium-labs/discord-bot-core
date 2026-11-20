"""The discord.py translator backed by a list of :class:`TranslationCatalog`."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands

from discord_bot_core.i18n.catalog import TranslationCatalog

__all__ = ["CoreTranslator"]

logger = logging.getLogger(__name__)


class CoreTranslator(app_commands.Translator):
    """Translate ``locale_str`` keys from a list of catalogs.

    Catalogs are searched in order; the first one holding the key wins. When the
    requested locale is missing, the lookup falls back to ``default_locale``.
    When nothing matches, :meth:`translate` returns ``None`` so discord.py keeps
    the original (English) string.

    Example:
        >>> translator = CoreTranslator([CORE_CATALOG])  # doctest: +SKIP
        >>> await bot.tree.set_translator(translator)  # doctest: +SKIP
    """

    def __init__(
        self,
        catalogs: list[TranslationCatalog] | None = None,
        default_locale: discord.Locale = discord.Locale.american_english,
    ) -> None:
        """Create the translator.

        Args:
            catalogs: The catalogs, searched in order; defaults to none.
            default_locale: The locale used when a key has no translation for the
                requested one. Defaults to ``en-US``.
        """
        super().__init__()
        self.catalogs: list[TranslationCatalog] = list(catalogs or [])
        self.default_locale = default_locale

    @property
    def supported_locales(self) -> frozenset[discord.Locale]:
        """Every locale present in any of the catalogs (including the default).

        Returns:
            The union of the catalogs' locales plus :attr:`default_locale`.
        """
        locales: set[discord.Locale] = {self.default_locale}
        for catalog in self.catalogs:
            locales |= catalog.locales()
        return frozenset(locales)

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: Any,
    ) -> str | None:
        """Translate ``string`` for ``locale``.

        Args:
            string: The ``locale_str`` whose ``.message`` is the symbolic key.
            locale: The locale discord.py asks for (the invoking user's, at
                runtime, or one of :attr:`supported_locales` at sync time).
            context: The discord.py translation context (unused).

        Returns:
            The translation, or ``None`` when no catalog has it (so discord.py
            keeps the original string).
        """
        key = string.message
        for catalog in self.catalogs:
            text = catalog.get(key, locale)
            if text is not None:
                return text
        for catalog in self.catalogs:
            text = catalog.get(key, self.default_locale)
            if text is not None:
                return text
        return None

    async def load(self) -> None:
        """Load the translator; a no-op beyond logging."""
        logger.debug(
            "CoreTranslator loaded locales=%s",
            ", ".join(sorted(locale.value for locale in self.supported_locales)),
        )

    async def unload(self) -> None:
        """Unload the translator; a no-op beyond logging."""
        logger.debug("CoreTranslator unloaded")

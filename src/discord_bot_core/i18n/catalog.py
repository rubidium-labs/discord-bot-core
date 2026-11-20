"""One catalog of translations: symbolic keys mapped to per-locale strings."""

from __future__ import annotations

import discord


class TranslationCatalog:
    """A group of message keys, each with its translations per locale.

    Keys are symbolic (``"core.sync.done"``) and are the same string passed to
    :func:`discord.app_commands.locale_str` at the call site. The value for a
    locale is a plain string; the ``en-US`` entry is the default English text used
    when a locale has no entry of its own.

    Example:
        >>> catalog = TranslationCatalog()
        >>> catalog.register("core.sync.done", {"en-US": "Done.", "fr": "Terminé."})
        >>> catalog.get("core.sync.done", discord.Locale.french)
        'Terminé.'
    """

    def __init__(self) -> None:
        """Create an empty catalog."""
        self._messages: dict[str, dict[str, str]] = {}

    def register(self, key: str, translations: dict[str, str]) -> None:
        """Add the translations of one key, replacing any previous entry.

        Args:
            key: The symbolic key, the one carried by ``locale_str``.
            translations: Translations keyed by locale code (``"en-US"``, ``"fr"``).

        Raises:
            ValueError: If ``translations`` is empty or a locale code is unknown.
        """
        if not translations:
            raise ValueError(f"Catalog entry {key!r} has no translations.")
        for code in translations:
            if not code:
                raise ValueError(f"Catalog entry {key!r} has an empty locale code.")
        self._messages[key] = dict(translations)

    def get(self, key: str, locale: discord.Locale) -> str | None:
        """Return the translation of ``key`` for ``locale``.

        Args:
            key: The symbolic key.
            locale: The locale to translate into.

        Returns:
            The string for that locale, or ``None`` if the key is unknown or has
            no translation for it.
        """
        translations = self._messages.get(key)
        if translations is None:
            return None
        return translations.get(locale.value)

    def locales(self) -> frozenset[discord.Locale]:
        """Return every locale for which the catalog has a translation.

        Unknown locale codes (not in :class:`discord.Locale`) are dropped.

        Returns:
            The set of locales present in the catalog.
        """
        codes = {
            code for translations in self._messages.values() for code in translations
        }
        locales: set[discord.Locale] = set()
        for code in codes:
            try:
                locales.add(discord.Locale(code))
            except ValueError:
                continue
        return frozenset(locales)

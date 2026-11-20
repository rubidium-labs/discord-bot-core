"""The core's own translations.

This catalog holds the strings the core itself prints at runtime (the ``/core``
cog's replies). It is intentionally small; later PRs fill it as user-facing
strings are converted. Keys are symbolic and mirrored at the call site with
:func:`discord.app_commands.locale_str`.
"""

from __future__ import annotations

from discord_bot_core.i18n.catalog import TranslationCatalog

CORE_CATALOG = TranslationCatalog()
"""The core's translations, keyed by symbolic message key."""

CORE_CATALOG.register(
    "core.sync.done",
    {
        "en-US": "Commands synced",
        "fr": "Commandes synchronisées",
    },
)

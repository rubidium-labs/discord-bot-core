"""Catalog-based translation for slash-command descriptions and runtime replies.

Command *names* are never translated; only descriptions (at sync time) and the
responses the bot sends (at runtime, per invoking user's locale). Register the
:class:`CoreTranslator` on the tree with ``await bot.tree.set_translator(...)``;
:class:`~discord_bot_core.bot.CoreBot` does this for you in ``setup_hook``.

Importing this package has no side effects beyond building the small core catalog.
"""

from discord_bot_core.i18n.catalog import TranslationCatalog
from discord_bot_core.i18n.core_catalog import CORE_CATALOG
from discord_bot_core.i18n.runtime import default_text, translate, use_catalogs
from discord_bot_core.i18n.translator import CoreTranslator

__all__ = [
    "CORE_CATALOG",
    "CoreTranslator",
    "TranslationCatalog",
    "default_text",
    "translate",
    "use_catalogs",
]

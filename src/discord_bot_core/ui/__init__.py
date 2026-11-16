"""The UI kit: embeds, the status message, views and modals.

``ui`` builds Discord messages and components; it never imports
``infrastructure``, and business logic never imports it.
"""

from discord_bot_core.ui.embeds import (
    EmbedField,
    error_embed,
    info_embed,
    success_embed,
    truncate,
    warning_embed,
)
from discord_bot_core.ui.status import (
    InteractionEditor,
    MessageEditor,
    StatusMessage,
    StatusProgress,
)
from discord_bot_core.ui.theme import DEFAULT_THEME, EmbedTheme
from discord_bot_core.ui.views import BaseModal, BaseView, SingleUserView

__all__ = [
    "DEFAULT_THEME",
    "BaseModal",
    "BaseView",
    "EmbedField",
    "EmbedTheme",
    "InteractionEditor",
    "MessageEditor",
    "SingleUserView",
    "StatusMessage",
    "StatusProgress",
    "error_embed",
    "info_embed",
    "success_embed",
    "truncate",
    "warning_embed",
]

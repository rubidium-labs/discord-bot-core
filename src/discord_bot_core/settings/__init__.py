"""Settings: validated configuration, loaded once at start.

Importing this package has no side effects; nothing is read until
:func:`load` or a constructor call.
"""

from discord_bot_core.settings.core import (
    DEFAULT_SECRETS_DIR,
    CoreSettings,
    Environment,
)

__all__ = ["DEFAULT_SECRETS_DIR", "CoreSettings", "Environment", "load"]

load = CoreSettings.load

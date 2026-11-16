"""HTTP clients for outside APIs.

The base lives here so every future client (for example a Top.gg-like API) shares
the same session, timeout and error handling instead of repeating it.
"""

from discord_bot_core.infrastructure.clients.base import BaseHttpClient

__all__ = ["BaseHttpClient"]

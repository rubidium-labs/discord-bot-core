"""The base every Rubidium Labs Discord bot is built on.

Importing this package has no side effects: it creates no settings object, no bot
and no database engine. Everything is constructed explicitly by the application's
composition root.

The public API is re-exported here as the library grows. For now only the version
is available.
"""

from importlib.metadata import version

__version__: str = version("discord-bot-core")

__all__ = ["__version__"]

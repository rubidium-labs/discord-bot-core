"""Extensions: discovery and the manager that loads them into the bot.

Importing this package has no side effects; nothing is imported from the target
package until :func:`discover_extensions` or a manager call runs.
"""

from discord_bot_core.extensions.discovery import discover_extensions
from discord_bot_core.extensions.manager import ExtensionManager, LoadReport

__all__ = ["ExtensionManager", "LoadReport", "discover_extensions"]

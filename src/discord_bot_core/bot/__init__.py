"""The bot: a ``commands.Bot`` subclass and its command tree.

Importing this package has no side effects; a bot is built explicitly by the
application's composition root.
"""

from discord_bot_core.bot.core_bot import CoreBot
from discord_bot_core.bot.tree import CoreCommandTree

__all__ = ["CoreBot", "CoreCommandTree"]

"""The core's admin commands: the ``/core`` group, its sync and extension commands.

The group is added to the tree scoped to the dev guild by
:meth:`discord_bot_core.bot.CoreBot.setup_hook`, so ``/core`` exists only there, in
dev and in prod alike. Every command is owner-only (the group carries the
:func:`~discord_bot_core.commands.owner_only` check) and replies ephemerally.
"""

from discord_bot_core.commands.admin._cog import CoreCog

__all__ = ["CoreCog"]

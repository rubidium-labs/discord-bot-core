"""A cog using postponed annotations (regression for the ``__globals__`` fact)."""

from __future__ import annotations

import discord
from discord import app_commands

from discord_bot_core.commands import transactional


class FutureCog:
    """A cog whose annotations are strings, resolved by discord.py at construction."""

    @app_commands.command(name="future", description="Postponed annotations.")
    @transactional
    async def future(self, interaction: discord.Interaction, participants: str) -> None:
        """Do nothing; only the constructed command is inspected."""

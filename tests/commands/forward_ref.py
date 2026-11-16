"""A module *without* postponed annotations, referencing a name defined only later.

``inspect.signature(func, eval_str=True)`` raises ``NameError`` here, so
``@transactional`` exercises its fallback to the unevaluated signature.
"""

import discord


async def command(
    interaction: discord.Interaction,
    value: "NotYetDefined",  # noqa: F821, UP037
) -> None:
    """Reference ``NotYetDefined`` before it is defined."""

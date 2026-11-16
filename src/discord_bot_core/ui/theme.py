"""The embed theme: the colours and footer shared by an application's embeds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import discord


@dataclass(frozen=True, slots=True)
class EmbedTheme:
    """The colours and optional footer for an application's embeds.

    Applications build their own theme and pass it explicitly to the embed helpers;
    :data:`DEFAULT_THEME` is a frozen module constant, not shared mutable state.

    Attributes:
        info: The colour for informational embeds.
        success: The colour for success embeds.
        warning: The colour for warning embeds.
        error: The colour for error embeds.
        footer: The footer text applied to every embed, or ``None``.
    """

    info: discord.Colour
    success: discord.Colour
    warning: discord.Colour
    error: discord.Colour
    footer: str | None = None


DEFAULT_THEME: Final[EmbedTheme] = EmbedTheme(
    info=discord.Colour.blurple(),
    success=discord.Colour.green(),
    warning=discord.Colour.orange(),
    error=discord.Colour.red(),
)
"""The theme used when the caller does not pass one."""

__all__ = ["DEFAULT_THEME", "EmbedTheme"]

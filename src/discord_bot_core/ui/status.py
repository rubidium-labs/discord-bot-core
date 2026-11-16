"""The status message: one message edited at each step of a long command.

The message is rendered by a pure :class:`StatusRenderer` and sent through a
:class:`MessageEditor`, so tests use a recording editor instead of a fake of
discord.py internals. Edits are throttled and serialised, and the final one always
wins.

Example:
    >>> status = StatusMessage.for_interaction(  # doctest: +SKIP
    ...     interaction, title="Job"
    ... )
    >>> await status.start("Received")  # doctest: +SKIP
    >>> async with status.progress("Sending", total=10) as progress:  # doctest: +SKIP
    ...     await progress.advance()  # doctest: +SKIP
    >>> await status.finish(text="Done")  # doctest: +SKIP
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

import discord

from discord_bot_core.ui.embeds import (
    EmbedField,
    error_embed,
    info_embed,
    success_embed,
)
from discord_bot_core.ui.theme import DEFAULT_THEME, EmbedTheme

logger = logging.getLogger(__name__)

DONE_PREFIX = "✅"
PENDING_PREFIX = "⏳"
BAR_FILLED = "█"
BAR_EMPTY = "░"
DEFAULT_BAR_WIDTH = 10

__all__ = [
    "BAR_EMPTY",
    "BAR_FILLED",
    "DEFAULT_BAR_WIDTH",
    "DONE_PREFIX",
    "PENDING_PREFIX",
    "InteractionEditor",
    "MessageEditor",
    "StatusMessage",
    "StatusProgress",
    "StatusRenderer",
]


class MessageEditor(Protocol):
    """The seam between the status message and Discord.

    The Discord adapter (:class:`InteractionEditor`) and a test recorder both
    implement it.
    """

    async def send(self, embed: discord.Embed) -> None:
        """Post the first message."""
        ...

    async def edit(self, embed: discord.Embed) -> None:
        """Replace the message with ``embed``."""
        ...


class InteractionEditor:
    """A :class:`MessageEditor` over a ``discord.Interaction``.

    Uses ``response.send_message`` when the interaction is unanswered and
    ``edit_original_response`` when it was deferred; it never calls the response
    twice.

    Attributes:
        interaction: The interaction.
        ephemeral: Whether the first message is ephemeral.
    """

    def __init__(
        self, interaction: discord.Interaction, *, ephemeral: bool = True
    ) -> None:
        """Create the editor.

        Args:
            interaction: The interaction whose message is edited.
            ephemeral: Whether the first message is ephemeral.
        """
        self.interaction = interaction
        self.ephemeral = ephemeral

    async def send(self, embed: discord.Embed) -> None:
        """Post the first message, or edit the deferred response.

        Args:
            embed: The embed to show.
        """
        response = self.interaction.response
        if response.is_done():
            await self.interaction.edit_original_response(embed=embed)
        else:
            await response.send_message(embed=embed, ephemeral=self.ephemeral)

    async def edit(self, embed: discord.Embed) -> None:
        """Replace the message with ``embed``.

        Args:
            embed: The embed to show.
        """
        await self.interaction.edit_original_response(embed=embed)


class StatusRenderer:
    """Turn status state into an embed; it performs no I/O.

    Attributes:
        title: The embed title.
        theme: The theme providing the colours and footer.
        bar_width: The number of cells in the progress bar.
    """

    def __init__(
        self,
        title: str,
        *,
        theme: EmbedTheme = DEFAULT_THEME,
        bar_width: int = DEFAULT_BAR_WIDTH,
    ) -> None:
        """Create the renderer.

        Args:
            title: The embed title.
            theme: The theme providing the colours and footer.
            bar_width: The number of cells in the progress bar.
        """
        self.title = title
        self.theme = theme
        self.bar_width = bar_width

    def bar(self, done: int, total: int) -> str:
        """Render a progress bar.

        Args:
            done: The number of completed items.
            total: The total number of items.

        Returns:
            The bar, for example ``"███░░░░░░░"``.
        """
        if total <= 0:
            return ""
        ratio = min(max(done / total, 0.0), 1.0)
        filled = round(ratio * self.bar_width)
        return BAR_FILLED * filled + BAR_EMPTY * (self.bar_width - filled)

    def render(
        self,
        *,
        steps: Sequence[str] = (),
        current: str | None = None,
        progress: tuple[str, int, int] | None = None,
        summary: Sequence[EmbedField] = (),
        text: str | None = None,
        footer: str | None = None,
        final: str | None = None,
    ) -> discord.Embed:
        """Render the current state into an embed.

        Args:
            steps: The completed steps, shown as check lines.
            current: The step in progress, shown as a pending line.
            progress: ``(label, done, total)`` for a progress bar, or ``None``.
            summary: The final summary fields.
            text: The description text, overriding the generated lines.
            footer: A footer overriding the theme's.
            final: ``"success"`` or ``"error"`` for a final embed, or ``None``.

        Returns:
            The embed.
        """
        if final == "success":
            embed = success_embed(self.title, text, fields=summary)
        elif final == "error":
            embed = error_embed(self.title, text, fields=summary)
        else:
            lines = [f"{DONE_PREFIX} {step}" for step in steps]
            if current is not None:
                lines.append(f"{PENDING_PREFIX} {current}")
            if progress is not None:
                label, done, total = progress
                lines.append(f"{label}… {done}/{total} {self.bar(done, total)}")
            description = text if text is not None else "\n".join(lines)
            embed = info_embed(self.title, description or None, fields=summary)
        if footer is not None:
            embed.set_footer(text=footer)
        return embed


class StatusProgress:
    """The progress handle returned by :meth:`StatusMessage.progress`.

    Use it as an async context manager and call :meth:`advance` for each item; the
    context manager's exit flushes the final state.

    Attributes:
        label: The progress label.
        total: The total number of items.
        done: The number of completed items.
    """

    def __init__(self, status: StatusMessage, label: str, total: int) -> None:
        """Create the handle.

        Args:
            status: The owning status message.
            label: The progress label.
            total: The total number of items.
        """
        self.status = status
        self.label = label
        self.total = total
        self.done = 0

    async def __aenter__(self) -> StatusProgress:
        """Show the progress bar at zero."""
        await self.status._set_progress(self.label, self.done, self.total, force=True)
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Flush the final progress state."""
        if exc[0] is None:
            await self.status._set_progress(
                self.label, self.done, self.total, force=True
            )

    async def advance(self, n: int = 1) -> None:
        """Record ``n`` completed items, editing at most once per interval.

        Args:
            n: The number of items completed.
        """
        self.done += n
        await self.status._set_progress(self.label, self.done, self.total)


class StatusMessage:
    """One message edited at each step of a long command.

    Attributes:
        title: The embed title.
        theme: The theme providing the colours and footer.
        min_edit_interval: The minimum number of seconds between throttled edits.
    """

    def __init__(
        self,
        editor: MessageEditor,
        *,
        title: str,
        theme: EmbedTheme = DEFAULT_THEME,
        min_edit_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Create the status message.

        Args:
            editor: Where the message is sent and edited.
            title: The embed title.
            theme: The theme providing the colours and footer.
            min_edit_interval: The minimum number of seconds between throttled
                edits; ``start``, ``step``, ``finish`` and ``fail`` always flush.
            clock: Monotonic clock, injectable for tests.
            sleep: Sleep function, injectable for tests.
        """
        self.editor = editor
        self.title = title
        self.theme = theme
        self.min_edit_interval = min_edit_interval
        self._clock = clock
        self._sleep = sleep
        self._renderer = StatusRenderer(title, theme=theme)
        self._lock = asyncio.Lock()
        self._steps: list[str] = []
        self._current: str | None = None
        self._progress: tuple[str, int, int] | None = None
        self._started = False
        self._finished = False
        self._last_edit: float | None = None
        self._editing_disabled = False

    @classmethod
    def for_interaction(
        cls,
        interaction: discord.Interaction,
        *,
        title: str,
        ephemeral: bool = True,
        **kwargs: object,
    ) -> StatusMessage:
        """Build a status message over an interaction.

        Args:
            interaction: The interaction whose message is edited.
            title: The embed title.
            ephemeral: Whether the first message is ephemeral.
            **kwargs: Passed to :class:`StatusMessage`.

        Returns:
            The status message.
        """
        return cls(
            InteractionEditor(interaction, ephemeral=ephemeral),
            title=title,
            **kwargs,  # type: ignore[arg-type]
        )

    def _embed(
        self,
        *,
        summary: Sequence[EmbedField] = (),
        text: str | None = None,
        footer: str | None = None,
        final: str | None = None,
    ) -> discord.Embed:
        return self._renderer.render(
            steps=self._steps,
            current=self._current,
            progress=self._progress,
            summary=summary,
            text=text,
            footer=footer,
            final=final,
        )

    def _ensure_active(self) -> None:
        if self._finished:
            msg = "the status message is already finished"
            raise RuntimeError(msg)

    async def _flush(self, embed: discord.Embed, *, first: bool) -> None:
        if self._editing_disabled:
            return
        try:
            if first:
                await self.editor.send(embed)
            else:
                await self.editor.edit(embed)
        except discord.HTTPException as exc:
            self._editing_disabled = True
            logger.warning("Status message edit failed, editing stopped: %s", exc)
            return
        self._last_edit = self._clock()

    async def start(self, text: str) -> None:
        """Post the message with the first step in progress.

        Args:
            text: The current step text.
        """
        self._ensure_active()
        async with self._lock:
            self._ensure_active()
            self._current = text
            self._started = True
            await self._flush(self._embed(), first=True)

    async def step(self, text: str) -> None:
        """Mark the current step done and show ``text`` as the new current step.

        Args:
            text: The new current step text.
        """
        self._ensure_active()
        async with self._lock:
            self._ensure_active()
            if self._current is not None:
                self._steps.append(self._current)
            self._current = text
            await self._flush(self._embed(), first=not self._started)
            self._started = True

    def progress(self, label: str, *, total: int) -> StatusProgress:
        """Return a progress handle.

        Args:
            label: The progress label.
            total: The total number of items.

        Returns:
            The progress handle.
        """
        self._ensure_active()
        return StatusProgress(self, label, total)

    async def _set_progress(
        self, label: str, done: int, total: int, *, force: bool = False
    ) -> None:
        self._ensure_active()
        async with self._lock:
            self._ensure_active()
            self._progress = (label, done, total)
            now = self._clock()
            if (
                not force
                and self._last_edit is not None
                and now - self._last_edit < self.min_edit_interval
            ):
                return
            await self._flush(self._embed(), first=not self._started)
            self._started = True

    async def finish(
        self,
        *,
        summary: Sequence[EmbedField] = (),
        text: str | None = None,
        footer: str | None = None,
    ) -> None:
        """Show the final success embed; always flushed.

        Args:
            summary: The summary fields.
            text: The description text, overriding the generated lines.
            footer: A footer overriding the theme's.
        """
        self._ensure_active()
        async with self._lock:
            self._ensure_active()
            self._finished = True
            embed = self._embed(
                summary=summary, text=text, footer=footer, final="success"
            )
            await self._flush(embed, first=not self._started)
            self._started = True

    async def fail(self, text: str) -> None:
        """Show the final error embed; always flushed.

        Args:
            text: The error description.
        """
        self._ensure_active()
        async with self._lock:
            self._ensure_active()
            self._finished = True
            embed = self._embed(text=text, final="error")
            await self._flush(embed, first=not self._started)
            self._started = True

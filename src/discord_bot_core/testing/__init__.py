"""Test doubles for applications built on the core.

The package imports no pytest: an application's tests get the fakes from here and
use whatever runner they like.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from discord_bot_core.infrastructure.database import Database


@dataclass
class SentMessage:
    """What a fake response or followup recorded.

    Attributes:
        content: The message content, if any.
        embed: The single embed, if any.
        embeds: The embeds, if any.
        ephemeral: Whether the message was ephemeral.
        view: The view attached to the message, if any.
        kind: ``"response"`` or ``"followup"``, so call order across both is visible.
    """

    content: str | None = None
    embed: Any = None
    embeds: list[Any] = field(default_factory=list)
    ephemeral: bool = False
    view: Any = None
    kind: str = "response"


class FakeResponse:
    """A fake ``discord.InteractionResponse`` recording what was sent."""

    def __init__(self) -> None:
        """Create an empty response."""
        self.sent: list[SentMessage] = []
        self._done = False

    def is_done(self) -> bool:
        """Return whether the initial response was already sent."""
        return self._done

    async def send_message(self, content: str | None = None, **kwargs: Any) -> None:
        """Record a message and mark the response as done.

        Args:
            content: The message content.
            **kwargs: ``embed``, ``embeds``, ``ephemeral`` and ``view`` are recorded.
        """
        self.sent.append(_record(content, kwargs, "response"))
        self._done = True


class FakeFollowup:
    """A fake ``discord.Webhook`` (``interaction.followup``) recording what was sent."""

    def __init__(self) -> None:
        """Create an empty followup."""
        self.sent: list[SentMessage] = []

    async def send(self, content: str | None = None, **kwargs: Any) -> None:
        """Record a followup message.

        Args:
            content: The message content.
            **kwargs: ``embed``, ``embeds``, ``ephemeral`` and ``view`` are recorded.
        """
        self.sent.append(_record(content, kwargs, "followup"))


def _record(content: str | None, kwargs: dict[str, Any], kind: str) -> SentMessage:
    embeds = list(kwargs.get("embeds") or ())
    embed = kwargs.get("embed")
    if embed is not None:
        embeds.insert(0, embed)
    return SentMessage(
        content=content,
        embed=embed,
        embeds=embeds,
        ephemeral=bool(kwargs.get("ephemeral", False)),
        view=kwargs.get("view"),
        kind=kind,
    )


@dataclass
class FakeUser:
    """A fake ``discord.User``: only the ``id`` the core reads."""

    id: int = 1


@dataclass
class FakeCommand:
    """A fake command: only the ``qualified_name`` the core reads."""

    qualified_name: str = "test"


class FakeClient:
    """A minimal ``interaction.client``.

    Attributes:
        extras: Arbitrary attributes (``database``, ``settings``, ...) set by
            keyword arguments or afterwards.
        channels: Channels returned by :meth:`get_channel`, keyed by id.
    """

    def __init__(self, **extras: Any) -> None:
        """Create the client.

        Args:
            **extras: Attributes stored on the client (for example ``database``).
        """
        self.extras: dict[str, Any] = dict(extras)
        self.channels: dict[int, Any] = {}
        for name, value in extras.items():
            setattr(self, name, value)

    def get_channel(self, channel_id: int) -> Any:
        """Return a channel from :attr:`channels`, or ``None``."""
        return self.channels.get(channel_id)

    async def fetch_channel(self, channel_id: int) -> Any:
        """Return a channel from :attr:`channels`, or ``None`` (no network)."""
        return self.channels.get(channel_id)


@dataclass
class FakeInteraction:
    """A fake ``discord.Interaction`` with the attributes the core reads.

    ``guild=None`` models a DM: ``guild_id`` is then ``None``.

    Attributes:
        extras: Arbitrary per-interaction state (``@transactional`` stores its session).
        client: The client, a :class:`FakeClient` by default.
        user: The invoking user.
        guild: The guild, or ``None`` in a DM.
        guild_id: ``guild.id``, or ``None`` in a DM (derived from ``guild``).
        channel_id: The channel id.
        command: The command, or ``None``.
        type: The interaction type.
        response: The fake response.
        followup: The fake followup.
    """

    extras: dict[str, Any] = field(default_factory=dict)
    client: FakeClient = field(default_factory=FakeClient)
    user: FakeUser = field(default_factory=FakeUser)
    guild: Any = None
    channel_id: int = 1
    command: FakeCommand | None = field(default_factory=FakeCommand)
    type: Any = None
    response: FakeResponse = field(default_factory=FakeResponse)
    followup: FakeFollowup = field(default_factory=FakeFollowup)
    guild_id: int | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        """Derive ``guild_id`` from ``guild``."""
        self.guild_id = self.guild.id if self.guild is not None else None


@asynccontextmanager
async def memory_database() -> AsyncIterator[Database]:
    """Yield a :class:`Database` on in-memory SQLite.

    The ``StaticPool`` makes every session see the same database. Create your tables
    from your ``Base.metadata`` before using it, and the engine is disposed on exit.

    Yields:
        A database on ``sqlite+aiosqlite:///:memory:``.
    """
    database = Database("sqlite+aiosqlite:///:memory:")
    try:
        yield database
    finally:
        await database.dispose()

"""The §12.5 table against a real ``memory_database()`` (SQLite ``:memory:``).

The other transactional tests drive the decorator with a fake database; these run the
same contract through the real
:class:`~discord_bot_core.infrastructure.database.Database` and assert on rows a
*second* session sees, so commit, rollback and close are what the engine does.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from discord_bot_core.commands import get_session, transactional
from discord_bot_core.commands.transactional import SESSION_KEY
from discord_bot_core.errors import NoActiveSessionError, UserFacingError
from discord_bot_core.infrastructure.database import Base, BaseRepository, Database
from discord_bot_core.testing import FakeClient, FakeInteraction, memory_database


class Widget(Base):
    """A tiny model created with ``Base.metadata.create_all`` on the test engine."""

    __tablename__ = "tx_widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class WidgetRepository(BaseRepository):
    """A repository holding the command's session (design §12.4)."""

    async def add(self, name: str) -> None:
        self._session.add(Widget(name=name))
        await self._session.flush()

    async def names(self) -> list[str]:
        result = await self._session.execute(select(Widget.name).order_by(Widget.id))
        return list(result.scalars())


class _CloseRecorder:
    """Wraps a real Database's ``session_factory`` to record ``close()`` calls.

    SQLAlchemy 2.1 keeps ``AsyncSession.is_active`` True after ``close()``, so the
    public, reliable signal is a spy on the session's own ``close`` method.
    ``Database.transaction`` builds sessions via ``self.session_factory()``, so
    patching the instance attribute is enough.
    """

    def __init__(self, database: Database) -> None:
        self._database = database
        self.closed_sessions: list[AsyncSession] = []
        original_factory = database.session_factory

        def recording_factory() -> AsyncSession:
            session = original_factory()
            original_close = session.close

            async def recording_close() -> None:
                self.closed_sessions.append(session)
                await original_close()

            session.close = recording_close  # type: ignore[method-assign]
            return session

        database.session_factory = recording_factory  # type: ignore[assignment]

    def wrap(self, database: Database) -> Database:
        """Return the database itself (already patched); kept for readability."""
        return database


@asynccontextmanager
async def _database() -> AsyncIterator[tuple[Database, _CloseRecorder]]:
    async with memory_database() as database:
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        recorder = _CloseRecorder(database)
        yield recorder.wrap(database), recorder
        # The engine is disposed when ``memory_database`` exits; the in-memory
        # database disappears with it, so there is nothing to drop or unregister.


def _interaction(database: Database) -> FakeInteraction:
    return FakeInteraction(client=FakeClient(database=database))


async def _names_after(database: Database) -> list[str]:
    async with database.transaction() as session:
        result = await session.execute(select(Widget.name).order_by(Widget.id))
        return list(result.scalars())


async def test_commit_on_success() -> None:
    async with _database() as (database, recorder):
        seen: list[AsyncSession] = []

        @transactional
        async def command(interaction: Any) -> None:
            session = get_session(interaction)
            seen.append(session)
            await WidgetRepository(session).add("gear")

        await command(_interaction(database))

        assert await _names_after(database) == ["gear"]
        assert seen[0] in recorder.closed_sessions


async def test_rollback_on_raise() -> None:
    async with _database() as (database, recorder):
        seen: list[AsyncSession] = []

        @transactional
        async def command(interaction: Any) -> None:
            session = get_session(interaction)
            seen.append(session)
            await WidgetRepository(session).add("gear")
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await command(_interaction(database))

        assert await _names_after(database) == []
        assert seen[0] in recorder.closed_sessions


async def test_rollback_on_user_facing_error() -> None:
    async with _database() as (database, _recorder):

        @transactional
        async def command(interaction: Any) -> None:
            await WidgetRepository(get_session(interaction)).add("gear")
            raise UserFacingError("Not enough participants.")

        with pytest.raises(UserFacingError):
            await command(_interaction(database))

        assert await _names_after(database) == []


async def test_session_closed_after_command() -> None:
    async with _database() as (database, recorder):
        seen: list[AsyncSession] = []

        @transactional
        async def command(interaction: Any) -> None:
            seen.append(get_session(interaction))

        await command(_interaction(database))

        assert seen[0] in recorder.closed_sessions


async def test_same_session_within_one_command() -> None:
    async with _database() as (database, _recorder):
        seen: list[AsyncSession] = []

        @transactional
        async def command(interaction: Any) -> None:
            seen.append(get_session(interaction))
            seen.append(get_session(interaction))

        await command(_interaction(database))

        assert seen[0] is seen[1]


async def test_different_session_per_invocation() -> None:
    async with _database() as (database, _recorder):
        seen: list[AsyncSession] = []

        @transactional
        async def command(interaction: Any) -> None:
            seen.append(get_session(interaction))

        await command(_interaction(database))
        await command(_interaction(database))

        assert seen[0] is not seen[1]


async def test_nested_decorated_call_reuses_session() -> None:
    async with _database() as (database, _recorder):
        seen: list[AsyncSession] = []

        @transactional
        async def inner(interaction: Any) -> None:
            seen.append(get_session(interaction))

        @transactional
        async def outer(interaction: Any) -> None:
            seen.append(get_session(interaction))
            await inner(interaction)

        await outer(_interaction(database))

        assert seen[0] is seen[1]


async def test_get_session_without_transactional_raises() -> None:
    async with _database() as (database, _recorder):

        async def command(interaction: Any) -> None:
            get_session(interaction)

        with pytest.raises(
            NoActiveSessionError, match="outside a @transactional command"
        ):
            await command(_interaction(database))


async def test_extras_cleaned_after_command() -> None:
    async with _database() as (database, _recorder):

        @transactional
        async def command(interaction: Any) -> None:
            assert SESSION_KEY in interaction.extras

        interaction = _interaction(database)
        await command(interaction)

        assert SESSION_KEY not in interaction.extras


async def test_cancellation_rolls_back() -> None:
    async with _database() as (database, recorder):
        started = asyncio.Event()
        seen: list[AsyncSession] = []

        @transactional
        async def command(interaction: Any) -> None:
            session = get_session(interaction)
            seen.append(session)
            await WidgetRepository(session).add("gear")
            started.set()
            await asyncio.sleep(3600)

        task = asyncio.create_task(command(_interaction(database)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert await _names_after(database) == []
        assert seen[0] in recorder.closed_sessions

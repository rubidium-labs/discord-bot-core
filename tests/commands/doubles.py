"""A minimal database double mimicking ``Database.transaction()`` (design §11).

``Database`` lives on an unmerged branch, so the tests drive the decorator with a fake
that has the same contract: commit on success, rollback on any ``BaseException`` and
close in every case. The fake session records its calls so tests can assert order.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class RecordingSession:
    """A fake ``AsyncSession`` recording ``commit``/``rollback``/``close`` calls."""

    def __init__(self, *, fail_commit: bool = False) -> None:
        self.calls: list[str] = []
        self.closed = False
        self.fail_commit = fail_commit
        self.rows: list[object] = []

    def add(self, row: object) -> None:
        """Stage a row (the fake has no unit of work; it appends on commit)."""
        self.rows.append(row)

    async def commit(self) -> None:
        """Record the commit, or raise when configured to fail."""
        self.calls.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit failed")

    async def rollback(self) -> None:
        """Record the rollback."""
        self.calls.append("rollback")

    async def close(self) -> None:
        """Record the close."""
        self.calls.append("close")
        self.closed = True


class FakeDatabase:
    """A fake ``Database`` whose ``transaction()`` follows the real contract."""

    def __init__(self, *, fail_commit: bool = False) -> None:
        self.fail_commit = fail_commit
        self.sessions: list[RecordingSession] = []

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[RecordingSession]:
        """Yield a session; commit on success, rollback on error, close always."""
        session = RecordingSession(fail_commit=self.fail_commit)
        self.sessions.append(session)
        try:
            yield session
            await session.commit()
        except BaseException:
            await asyncio.shield(session.rollback())
            raise
        finally:
            await asyncio.shield(session.close())


class Repository:
    """A repository holding the session, like ``BaseRepository`` (design §12.4)."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def add(self, row: object) -> None:
        self._session.add(row)

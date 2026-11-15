"""Tests for BaseRepository."""

from sqlalchemy.ext.asyncio import AsyncSession

from discord_bot_core.infrastructure.database import BaseRepository


def test_stores_session() -> None:
    session = AsyncSession()
    repository = BaseRepository(session)
    assert repository._session is session

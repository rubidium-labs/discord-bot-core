"""Tests for the Database engine, transaction boundary and SQLite specifics."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic import SecretStr
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from discord_bot_core.infrastructure.database import NAMING_CONVENTION, Base, Database


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"))


async def _create_tables(database: Database) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def _drop_tables(database: Database) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    db = Database("sqlite+aiosqlite:///:memory:")
    await _create_tables(db)
    try:
        yield db
    finally:
        await db.dispose()


def test_engine_built_from_string() -> None:
    db = Database("sqlite+aiosqlite:///:memory:")
    assert db.engine is not None
    assert db.session_factory.kw["expire_on_commit"] is False
    assert db.session_factory.kw["autoflush"] is True


def test_engine_built_from_secret() -> None:
    db = Database(SecretStr("sqlite+aiosqlite:///:memory:"))
    assert db.engine is not None


async def test_sqlite_foreign_keys_pragma_is_on(database: Database) -> None:
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(Child(parent_id=999))
            await session.flush()


async def test_transaction_commits_on_success(database: Database) -> None:
    async with database.transaction() as session:
        session.add(Parent(id=1, name="a"))

    async with database.transaction() as session:
        result = await session.execute(select(Parent).where(Parent.id == 1))
        assert result.scalar_one().name == "a"


async def test_transaction_rolls_back_on_exception(database: Database) -> None:
    error = RuntimeError("boom")
    with pytest.raises(RuntimeError) as caught:
        async with database.transaction() as session:
            session.add(Parent(id=1, name="a"))
            await session.flush()
            raise error
    assert caught.value is error

    async with database.transaction() as session:
        result = await session.execute(select(Parent))
        assert result.scalars().all() == []


async def test_transaction_rolls_back_on_cancellation(database: Database) -> None:
    started = asyncio.Event()

    async def body() -> None:
        async with database.transaction() as session:
            session.add(Parent(id=1, name="a"))
            await session.flush()
            started.set()
            await asyncio.sleep(10)

    task = asyncio.create_task(body())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async with database.transaction() as session:
        result = await session.execute(select(Parent))
        assert result.scalars().all() == []


async def test_transaction_closes_session_on_success(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []
    original_close = AsyncSession.close

    async def spy_close(self: AsyncSession) -> None:
        closed.append(True)
        await original_close(self)

    monkeypatch.setattr(AsyncSession, "close", spy_close)

    async with database.transaction() as session:
        session.add(Parent(id=1, name="a"))

    assert closed == [True]


async def test_transaction_closes_session_on_failure(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []
    original_close = AsyncSession.close

    async def spy_close(self: AsyncSession) -> None:
        closed.append(True)
        await original_close(self)

    monkeypatch.setattr(AsyncSession, "close", spy_close)

    with pytest.raises(RuntimeError):
        async with database.transaction():
            raise RuntimeError("boom")

    assert closed == [True]


async def test_commit_failure_propagates_and_rolls_back(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    rolled_back: list[bool] = []
    closed: list[bool] = []
    original_rollback = AsyncSession.rollback
    original_close = AsyncSession.close

    async def failing_commit(self: AsyncSession) -> None:
        raise RuntimeError("commit failed")

    async def spy_rollback(self: AsyncSession) -> None:
        rolled_back.append(True)
        await original_rollback(self)

    async def spy_close(self: AsyncSession) -> None:
        closed.append(True)
        await original_close(self)

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    monkeypatch.setattr(AsyncSession, "rollback", spy_rollback)
    monkeypatch.setattr(AsyncSession, "close", spy_close)

    with pytest.raises(RuntimeError, match="commit failed"):
        async with database.transaction() as session:
            session.add(Parent(id=1, name="a"))

    assert rolled_back == [True]
    assert closed == [True]


def test_naming_convention_applied() -> None:
    class Uniquely(Base):
        __tablename__ = "uniquely"

        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        code: Mapped[str] = mapped_column(String(10))
        __table_args__ = (UniqueConstraint("code"),)

    constraints = {c.name for c in Uniquely.__table__.constraints}
    assert "uq_uniquely_code" in constraints
    assert NAMING_CONVENTION["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    Base.metadata.remove(Uniquely.__table__)


async def test_ping(database: Database) -> None:
    await database.ping()


async def test_dispose() -> None:
    db = Database("sqlite+aiosqlite:///:memory:")
    await _create_tables(db)
    await db.dispose()


async def test_engine_kwargs_for_memory_use_static_pool() -> None:
    db = Database("sqlite+aiosqlite:///:memory:")
    assert type(db.engine.pool).__name__ == "StaticPool"
    await db.dispose()

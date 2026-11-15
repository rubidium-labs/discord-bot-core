"""The database engine, session factory and the single transaction boundary."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import SecretStr
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool


class Database:
    """An async engine, its session factory and the transaction context manager.

    A URL may be a :class:`~pydantic.SecretStr`, so a password never leaks through
    ``repr`` of the settings object. SQLite gets ``PRAGMA foreign_keys=ON`` on every
    connection; ``:memory:`` URLs use a :class:`~sqlalchemy.pool.StaticPool` so every
    session sees the same database.

    Attributes:
        engine: The async engine.
        session_factory: Creates sessions with ``expire_on_commit=False`` and
            ``autoflush=True``.
    """

    def __init__(self, url: str | SecretStr, *, pool_pre_ping: bool = True) -> None:
        """Build the engine and the session factory.

        Args:
            url: The SQLAlchemy async URL, as a string or a secret.
            pool_pre_ping: Whether to check pooled connections before use.
        """
        url_str = url.get_secret_value() if isinstance(url, SecretStr) else url
        kwargs: dict[str, object] = {"pool_pre_ping": pool_pre_ping}
        if url_str.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url_str:
                kwargs["poolclass"] = StaticPool
        self.engine: AsyncEngine = create_async_engine(url_str, **kwargs)
        if url_str.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _enable_foreign_keys)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=True
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Run a unit of work: commit on success, roll back on any exception.

        The only place that decides commit, rollback and close. ``BaseException``
        so a cancelled task also rolls back; ``shield`` so the clean-up is not
        itself cancelled half way.

        Yields:
            The session for this transaction.
        """
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except BaseException:
            await asyncio.shield(session.rollback())
            raise
        finally:
            await asyncio.shield(session.close())

    async def ping(self) -> None:
        """Check that the database answers (``SELECT 1``)."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        """Close every pooled connection and release the engine."""
        await self.engine.dispose()


def _enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

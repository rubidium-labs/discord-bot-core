"""The Alembic wiring helper an application's ``env.py`` calls.

The app owns ``alembic.ini``, ``alembic/`` and its models; the core owns the
settings the migrations run with, so every app's ``env.py`` is the same five lines
(design §11.1). The database URL is read from the app's settings and never written
to ``alembic.ini``, so a secret never lands in a file in git.

Example:
    >>> from alembic import context
    >>> from discord_bot_core.infrastructure.database import Base
    >>> from discord_bot_core.infrastructure.database.migrations import run_migrations
    >>> url = "sqlite+aiosqlite:///db.sqlite"
    >>> run_migrations(context, metadata=Base.metadata, url=url)  # doctest: +SKIP
"""

from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Protocol

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from discord_bot_core.errors import DatabaseNotConfiguredError

if TYPE_CHECKING:
    from sqlalchemy import MetaData
    from sqlalchemy.engine import Connection


class MigrationContext(Protocol):
    """The part of the Alembic ``context`` module :func:`run_migrations` uses."""

    def is_offline_mode(self) -> bool:
        """Return whether Alembic runs in offline (``--sql``) mode."""
        ...

    def configure(self, **kw: object) -> None:
        """Configure the migration context."""
        ...

    def begin_transaction(self) -> AbstractContextManager[None]:
        """Begin the migration transaction."""
        ...

    def run_migrations(self, **kw: object) -> None:
        """Run the migration scripts."""
        ...


def run_migrations(
    context: MigrationContext,
    *,
    metadata: MetaData,
    url: str | SecretStr | None,
) -> None:
    """Run Alembic in offline or online mode, from an app's ``env.py``.

    Offline mode (``alembic upgrade head --sql``) renders the SQL with literal binds;
    online mode runs the migrations on an async engine with a ``NullPool``. The URL is
    never written to ``alembic.ini``: it comes from the settings, so a secret stays out
    of the repository. SQLite uses batch mode (``render_as_batch=True``) for its
    ALTER limitations; type and server-default comparison are always on.

    Args:
        context: The Alembic ``context`` module (``from alembic import context``).
        metadata: The application's metadata (usually ``Base.metadata``).
        url: The SQLAlchemy async URL, as a string or a secret.

    Raises:
        DatabaseNotConfiguredError: If ``url`` is ``None`` or empty; the message names
            the ``database_url`` setting.

    Example:
        >>> url = settings.database_url
        >>> run_migrations(context, metadata=Base.metadata, url=url)  # doctest: +SKIP
    """
    url_str = url.get_secret_value() if isinstance(url, SecretStr) else url
    if not url_str:
        raise DatabaseNotConfiguredError(
            "Cannot run migrations: the database_url setting is not set. "
            "Set DATABASE_URL (or the database_url secret) before running Alembic."
        )

    render_as_batch = _is_sqlite(url_str)

    if context.is_offline_mode():
        context.configure(
            url=url_str,
            literal_binds=True,
            render_as_batch=render_as_batch,
            compare_type=True,
            compare_server_default=True,
            dialect_name=_dialect_name(url_str),
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    asyncio.run(_run_online(context, metadata=metadata, url_str=url_str))


async def _run_online(
    context: MigrationContext, *, metadata: MetaData, url_str: str
) -> None:
    """Run the migrations on an async engine with a :class:`NullPool`.

    Args:
        context: The Alembic ``context`` module.
        metadata: The application's metadata.
        url_str: The resolved database URL.
    """
    engine = create_async_engine(url_str, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(
                _do_run_migrations,
                context=context,
                metadata=metadata,
                render_as_batch=_is_sqlite(url_str),
            )
    finally:
        await engine.dispose()


def _do_run_migrations(
    connection: Connection,
    *,
    context: MigrationContext,
    metadata: MetaData,
    render_as_batch: bool,
) -> None:
    """Configure Alembic on a sync connection and run the migrations.

    Args:
        connection: The sync connection from ``connection.run_sync``.
        context: The Alembic ``context`` module.
        metadata: The application's metadata.
        render_as_batch: Whether to use batch mode (SQLite).
    """
    context.configure(
        connection=connection,
        target_metadata=metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=render_as_batch,
    )
    with context.begin_transaction():
        context.run_migrations()


def _dialect_name(url_str: str) -> str:
    """Return the SQLAlchemy dialect name of a URL.

    Args:
        url_str: A SQLAlchemy URL.

    Returns:
        The dialect before the driver, for example ``sqlite`` for
        ``sqlite+aiosqlite:///db``.
    """
    return url_str.split(":", 1)[0].split("+", 1)[0]


def _is_sqlite(url_str: str) -> bool:
    """Return whether a URL uses the SQLite dialect.

    Args:
        url_str: A SQLAlchemy URL.

    Returns:
        ``True`` for SQLite, which needs batch mode for ALTER.
    """
    return _dialect_name(url_str) == "sqlite"

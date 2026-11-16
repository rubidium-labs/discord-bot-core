"""Tests for the Alembic helper run_migrations()."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import Integer, MetaData, String, Table, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from discord_bot_core.errors import DatabaseNotConfiguredError
from discord_bot_core.infrastructure.database.migrations import run_migrations


def _sample_metadata() -> MetaData:
    metadata = MetaData()
    Table(
        "samples",
        metadata,
        *(
            _column("id", Integer, primary_key=True),
            _column("name", String(50), nullable=False),
        ),
    )
    return metadata


def _column(name: str, type_: Any, **kwargs: Any) -> Any:
    from sqlalchemy import Column

    return Column(name, type_, **kwargs)


class FakeContext:
    """A stand-in for the Alembic ``context`` module recording the calls."""

    def __init__(self, *, offline: bool) -> None:
        self.offline = offline
        self.configure_kwargs: list[dict[str, Any]] = []
        self.ran = False

    def is_offline_mode(self) -> bool:
        return self.offline

    def configure(self, **kw: Any) -> None:
        self.configure_kwargs.append(kw)

    def begin_transaction(self) -> FakeContext:
        return self

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None

    def run_migrations(self, **kw: Any) -> None:
        self.ran = True


def test_missing_url_raises_database_not_configured() -> None:
    with pytest.raises(DatabaseNotConfiguredError, match="database_url"):
        run_migrations(FakeContext(offline=True), metadata=MetaData(), url=None)


def test_empty_url_raises_database_not_configured() -> None:
    with pytest.raises(DatabaseNotConfiguredError, match="database_url"):
        run_migrations(FakeContext(offline=True), metadata=MetaData(), url="")


def test_offline_sqlite_configure_kwargs() -> None:
    context = FakeContext(offline=True)
    run_migrations(
        context,
        metadata=_sample_metadata(),
        url="sqlite+aiosqlite:///db.sqlite",
    )

    (kwargs,) = context.configure_kwargs
    assert kwargs["url"] == "sqlite+aiosqlite:///db.sqlite"
    assert kwargs["literal_binds"] is True
    assert kwargs["render_as_batch"] is True
    assert kwargs["compare_type"] is True
    assert kwargs["compare_server_default"] is True
    assert kwargs["dialect_name"] == "sqlite"
    assert context.ran is True


def test_offline_postgres_is_not_batch() -> None:
    context = FakeContext(offline=True)
    run_migrations(
        context,
        metadata=_sample_metadata(),
        url="postgresql+asyncpg://user:secret@localhost/db",
    )

    (kwargs,) = context.configure_kwargs
    assert kwargs["render_as_batch"] is False
    assert kwargs["dialect_name"] == "postgresql"


def test_secret_url_is_accepted() -> None:
    context = FakeContext(offline=True)
    run_migrations(
        context,
        metadata=_sample_metadata(),
        url=SecretStr("sqlite+aiosqlite:///db.sqlite"),
    )

    (kwargs,) = context.configure_kwargs
    assert kwargs["url"] == "sqlite+aiosqlite:///db.sqlite"


def test_online_runs_migrations_on_temp_sqlite(tmp_path: Path) -> None:
    script_location = _make_alembic_environment(tmp_path)
    database_path = tmp_path / "app.sqlite"
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", "")

    command.upgrade(config, "head")

    async def tables() -> list[str]:
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            async with engine.connect() as connection:
                return await connection.run_sync(
                    lambda sync: inspect(sync).get_table_names()
                )
        finally:
            await engine.dispose()

    names = asyncio.run(tables())
    assert "alembic_version" in names
    assert "samples" in names


def _make_alembic_environment(tmp_path: Path) -> Path:
    """Write a minimal alembic environment whose env.py calls run_migrations."""
    script_location = tmp_path / "alembic"
    versions = script_location / "versions"
    versions.mkdir(parents=True)
    database_path = tmp_path / "app.sqlite"

    (script_location / "env.py").write_text(
        "from alembic import context\n"
        "from sqlalchemy import Column, Integer, MetaData, String, Table\n"
        "from discord_bot_core.infrastructure.database.migrations import (\n"
        "    run_migrations,\n"
        ")\n"
        "\n"
        "metadata = MetaData()\n"
        "Table(\n"
        "    'samples',\n"
        "    metadata,\n"
        "    Column('id', Integer, primary_key=True),\n"
        "    Column('name', String(50), nullable=False),\n"
        ")\n"
        f"run_migrations(context, metadata=metadata, url='sqlite+aiosqlite:///{database_path}')\n"
    )
    (script_location / "script.py.mako").write_text(
        '"""${message}"""\n'
        "from alembic import op\n"
        "import sqlalchemy as sa\n"
        "${imports if imports else ''}\n"
        "revision = ${repr(up_revision)}\n"
        "down_revision = ${repr(down_revision)}\n"
        "branch_labels = ${repr(branch_labels)}\n"
        "depends_on = ${repr(depends_on)}\n"
        "\n"
        "def upgrade() -> None:\n"
        "    ${upgrades if upgrades else 'pass'}\n"
        "\n"
        "def downgrade() -> None:\n"
        "    ${downgrades if downgrades else 'pass'}\n"
    )
    (versions / "0001_initial.py").write_text(
        '"""initial"""\n'
        "from alembic import op\n"
        "import sqlalchemy as sa\n"
        "\n"
        "revision = '0001'\n"
        "down_revision = None\n"
        "branch_labels = None\n"
        "depends_on = None\n"
        "\n"
        "def upgrade() -> None:\n"
        "    op.create_table(\n"
        "        'samples',\n"
        "        sa.Column('id', sa.Integer(), primary_key=True),\n"
        "        sa.Column('name', sa.String(50), nullable=False),\n"
        "    )\n"
        "\n"
        "def downgrade() -> None:\n"
        "    op.drop_table('samples')\n"
    )
    return script_location


def test_offline_sql_renders_with_literal_binds(tmp_path: Path) -> None:
    script_location = _make_alembic_environment(tmp_path)
    database_path = tmp_path / "app.sqlite"
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", "")

    buffer = _StringIO()
    config.output_buffer = buffer  # type: ignore[assignment]
    command.upgrade(config, "head", sql=True)

    rendered = buffer.getvalue()
    assert "CREATE TABLE samples" in rendered
    assert "INSERT INTO alembic_version" in rendered
    assert not database_path.exists()


class _StringIO:
    """A minimal text buffer for Alembic's ``output_buffer``."""

    def __init__(self) -> None:
        self._parts: list[str] = []

    def write(self, text: str) -> None:
        self._parts.append(text)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        return "".join(self._parts)

    def __enter__(self) -> _StringIO:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_alembic_version_row_recorded(tmp_path: Path) -> None:
    script_location = _make_alembic_environment(tmp_path)
    database_path = tmp_path / "app.sqlite"
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", "")

    command.upgrade(config, "head")

    async def revision() -> str:
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text("SELECT version_num FROM alembic_version")
                )
                return str(result.scalar_one())
        finally:
            await engine.dispose()

    assert asyncio.run(revision()) == "0001"

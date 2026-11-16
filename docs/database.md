# Database

The core ships the database primitives an app builds on: an async engine with a single
transaction boundary, a declarative `Base` with a naming convention, a `BaseRepository`,
and an Alembic helper. The app owns its models and its migrations. See
[design section 11](design.md#11-database-infrastructure) and
[section 12](design.md#12-the-transactional-session-per-command) for the reasoning.

`discord_bot_core.infrastructure.database` imports no `discord`: it is usable from an
Alembic `env.py` and from scripts.

## `Database`

```python
from discord_bot_core.infrastructure.database import Database

database = Database(settings.database_url)          # str or SecretStr
async with database.transaction() as session:       # commit on success, rollback on error
    session.add(draw)
await database.ping()                               # SELECT 1
await database.dispose()                            # close pooled connections
```

- `transaction()` is the **only** place that decides commit, rollback and close. It rolls
  back on any `BaseException` (so a cancelled command also rolls back) and closes the
  session in every case. The commit is on the success path only, never in `finally`.
- `expire_on_commit=False`: after commit the command still reads result objects to build
  its reply (an async session cannot lazy-load an expired attribute).
- SQLite: `PRAGMA foreign_keys=ON` on every connection; `:memory:` URLs use a
  `StaticPool` so every session sees the same database.
- A `SecretStr` URL keeps the password out of `repr`; the core calls
  `.get_secret_value()` only when it builds the engine.

`CoreBot` builds a `Database` only if `settings.database_url` is set; otherwise
`bot.database is None` and nothing imports a driver. The core never creates tables and
never runs migrations at start.

## Models

Models inherit from the core's `Base`. It carries a naming convention, so constraint
names are deterministic and Alembic can drop and alter them (in particular with SQLite
batch mode).

```python
# src/my_bot/infrastructure/database/models.py
from sqlalchemy.orm import Mapped, mapped_column

from discord_bot_core.infrastructure.database import Base


class Draw(Base):
    __tablename__ = "draws"

    id: Mapped[int] = mapped_column(primary_key=True)
    giver_id: Mapped[int]
    receiver_id: Mapped[int]
```

Repositories take the session in their constructor and never commit:

```python
from discord_bot_core.infrastructure.database import BaseRepository


class DrawRepository(BaseRepository):
    async def add(self, draw: Draw) -> None:
        self._session.add(draw)
        await self._session.flush()
```

## The per-command session (`@transactional`)

A command gets one session for its whole body from `@transactional`, and reads it with
`get_session(interaction)`. The decorator adds **no** slash-command option: the signature
is untouched.

```python
import discord
from discord import app_commands
from discord.ext import commands

from discord_bot_core.commands import get_session, transactional


class DrawCog(commands.Cog):
    @app_commands.command(name="draw", description="Draw names.")
    @transactional
    async def draw(self, interaction: discord.Interaction, participants: str) -> None:
        session = get_session(interaction)
        repository = DrawRepository(session)
        ...
```

- Order: `@app_commands.command` outermost, `@transactional` directly above the `def`
  (anywhere under `@app_commands.command` works).
- Commit on success, roll back on any exception, close in every case.
- Repositories and services take the session in their constructor; they never open their
  own transaction and never commit.
- To make data durable before the final user-facing message, call `await
  session.commit()` explicitly; the session stays usable (a new transaction begins).
- A bot without a database raises `DatabaseNotConfiguredError` at the first command
  invocation, naming `database_url`.

## Alembic

The app owns `alembic.ini`, `alembic/` and its models. The core owns the wiring helper, so
`env.py` is five lines and uses the same settings (and secrets files) as the bot. The URL
is **not** put in `alembic.ini` (`sqlalchemy.url` stays empty or commented), so a secret
never lands in a file in git.

`alembic/env.py`:

```python
from alembic import context
from discord_bot_core.infrastructure.database import Base
from discord_bot_core.infrastructure.database.migrations import run_migrations
from my_bot.infrastructure.database import models  # noqa: F401  (registers tables on Base.metadata)
from my_bot.settings import AppSettings

settings = AppSettings.load()
run_migrations(context, metadata=Base.metadata, url=settings.database_url)
```

`run_migrations(context, *, metadata, url)`:

- `url` may be a `str`, a `SecretStr` or `None`. Missing or empty → `DatabaseNotConfiguredError`
  naming `database_url` (no traceback noise).
- Offline (`alembic upgrade head --sql`): `context.configure(url=..., literal_binds=True)`
  with the dialect derived from the URL.
- Online: an async engine with a `NullPool`, `connection.run_sync(...)`, run with
  `asyncio.run`; the engine is disposed in `finally`.
- `render_as_batch=True` when the URL dialect is SQLite (ALTER limitations),
  `compare_type=True`, `compare_server_default=True`.

Minimal `alembic.ini` (the URL is deliberately absent):

```ini
[alembic]
script_location = alembic
# sqlalchemy.url is deliberately not set: alembic/env.py reads it from AppSettings
```

Create a revision after changing a model:

```bash
uv run alembic revision --autogenerate -m "add draws"
uv run alembic upgrade head
```

Deploy: run `alembic upgrade head` as a separate one-off container command (same image,
same `/run/secrets`), then start the bot. Nothing runs migrations at bot start.

## Tests: `memory_database()`

`testing.memory_database()` yields a `Database` on in-memory SQLite with a `StaticPool`
(every session sees the same database) and disposes the engine on exit. Create your
tables from your metadata first:

```python
from discord_bot_core.infrastructure.database import Base
from discord_bot_core.testing import memory_database


async def test_draw_round_trip() -> None:
    async with memory_database() as db:
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with db.transaction() as session:
            session.add(Draw(id=1, giver_id=10, receiver_id=11))

        async with db.transaction() as session:
            assert await session.get(Draw, 1) is not None
```

For a command test, pass the database on a fake client:
`FakeInteraction(client=FakeClient(database=db))`. More in [testing](testing.md).

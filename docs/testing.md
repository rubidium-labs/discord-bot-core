# Testing a bot built on discord-bot-core

None of this needs Discord, a token or the network. The library ships its fakes in
`discord_bot_core.testing` (it imports no pytest, so it works with any runner); the design
is in [design section 15](design.md#15-testing-support).

## Setup

Dev dependencies of your app: `pytest`, `pytest-asyncio`, `pytest-cov`. Use
pytest-asyncio's **auto mode**, so `async def test_...` needs no marker:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=my_bot --cov-report=term-missing"
```

Coverage is reported on every `uv run pytest` (term + xml). There is deliberately no
`fail_under` threshold: tests exist to find problems, not to hit a number — test the
business logic thoroughly, the rest follows.

## Settings: build them by constructor

Never rely on the environment or on a `.env` file in tests.

```python
from pydantic import SecretStr
from my_bot.settings import AppSettings

def make_settings(**overrides) -> AppSettings:
    return AppSettings(
        _env_file=None,                      # ignore any local .env
        discord_token=SecretStr("test-token"),
        dev_guild_id=1,
        greeting="hi",                       # your own required setting
        **overrides,
    )
```

Test the settings themselves the same way: a missing required field raises
`pydantic.ValidationError`, and `repr(settings)` does not contain the token.

## Fake interactions

`FakeInteraction` has the attributes the core reads: `extras`, `client`, `user`,
`guild_id`, `guild`, `channel_id`, `command`, `type`, `response`, `followup`.
`FakeResponse` and `FakeFollowup` record what was sent (content, embed, ephemeral flag,
order of calls).

```python
from discord_bot_core.testing import FakeInteraction

async def test_hello_replies_ephemeral() -> None:
    interaction = FakeInteraction()                  # a guild interaction
    await HelloCog(make_settings()).hello.callback(cog, interaction, name="Ada")

    sent = interaction.response.sent[0]
    assert sent.ephemeral is True
    assert "Ada" in sent.content
```

Cover DMs too: `FakeInteraction(guild=None)` gives `guild_id is None`, which is how
real DM interactions look. Commands must not assume a guild.

Call the command's callback directly (`cmd.callback(cog, interaction, ...)`); you test
your cog's behaviour without going through the command tree.

## A database in memory

`memory_database()` yields a `Database` on in-memory SQLite (a `StaticPool`, so every
session sees the same data). Create your tables from your `Base.metadata`:

```python
from discord_bot_core.testing import FakeInteraction, memory_database
from discord_bot_core.infrastructure.database import Base

async def test_draw_is_recorded() -> None:
    async with memory_database() as db:
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        interaction = FakeInteraction(client=FakeClient(database=db))
        await cog.secret_santa.callback(cog, interaction, participants="...")

        async with db.transaction() as session:      # a new session sees the committed data
            assert await DrawRepository(session).count() == 1
```

(`FakeClient` is exported by the same module: a minimal `interaction.client` with
`database`, `settings` and `error_handler`.)

## The per-command session (`@transactional`)

Commands decorated with `@transactional` get their session from
`get_session(interaction)`. With `FakeInteraction(client=FakeClient(database=db))` the
decorator behaves as in production. The core tests the following; test the same for your
own commands that write:

| Test | What it proves |
|---|---|
| commit on success | the row is visible to a new session; the body's session is closed |
| rollback on exception | the exception propagates unchanged; no row; session closed |
| rollback on `UserFacingError` | domain errors are failures too |
| no commit after rollback | a spy session sees `rollback`, `close`, never `commit` |
| two repositories, one transaction | both share one session; both rows commit, or neither |
| partial progress with early commit | the write before `await session.commit()` persists, later ones do not |
| session is not an option | `[p.name for p in command.parameters]` lists only your options, also with `from __future__ import annotations` |
| signature unchanged | `inspect.signature(wrapped) == inspect.signature(original, eval_str=True)` |
| `get_session` outside a transaction | `NoActiveSessionError` |
| database not configured | `DatabaseNotConfiguredError` naming `database_url`; the body never ran |
| cancellation rolls back | cancel the task mid-body: no row, session closed, `CancelledError` propagates |
| extras cleaned | the session key is gone from `interaction.extras` after success and failure |
| concurrent commands | two commands under `asyncio.gather` have different sessions; one failing does not roll back the other |
| commit failure propagates | a failing `commit` raises, rollback is attempted, the session is closed |
| error path end to end | a `UserFacingError` through a real `CoreCommandTree.on_error` sends an ephemeral message and rolls back |

For your own app, the first three, "two repositories, one transaction" and "session is not
an option" are the ones worth writing for each command.

## StatusMessage with a recording editor

`StatusMessage` talks to a `MessageEditor` (a `Protocol` with `send(embed)` and
`edit(embed)`), so tests use a recorder, not a mock of discord.py. Inject `clock` and
`sleep` so throttling is instant and deterministic:

```python
import discord
from discord_bot_core.ui.status import StatusMessage

class RecordingEditor:
    def __init__(self) -> None:
        self.embeds: list[discord.Embed] = []
    async def send(self, embed: discord.Embed) -> None:
        self.embeds.append(embed)
    async def edit(self, embed: discord.Embed) -> None:
        self.embeds.append(embed)

async def test_flow() -> None:
    editor = RecordingEditor()
    now = 0.0
    async def no_sleep(_: float) -> None: ...
    status = StatusMessage(editor, title="Job", clock=lambda: now, sleep=no_sleep)

    await status.start("Received")
    await status.step("Working…")
    await status.finish(text="Done")

    assert len(editor.embeds) == 3
    assert "Done" in (editor.embeds[-1].description or "")
```

Assert on the final embed's fields, on the ordering (a late progress edit never overwrites
the final one), and that nothing private (who gives to whom, in Secret Santa) appears in
any embed.

## Other seams

- `CoreBot(settings, database=db, error_handler=...)` can be built in a test with no
  connection (`discord.Client.__init__` does no I/O). Do not call `bot.start()` or `run()`.
- Services have no discord.py import: test them with plain objects and a fake repository or
  `memory_database()`. Pure functions (such as a draw) need no fixtures; use `random.Random(seed)`
  injected for determinism, and many seeds and sizes.
- Check that the app imports without side effects (no bot, engine or settings created).

## Running

```bash
uv run pytest                 # tests + coverage report
uv run pytest -k transactional
uv run pytest --cov-report=xml
```

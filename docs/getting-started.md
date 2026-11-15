# Getting started

From zero to a running bot with one cog. The example app is called `my_bot`; replace the
name. Nothing here is released yet: the API shown is the one decided in
[design.md](design.md), and the tag in the dependency line is the target release.

You need Python 3.14, [uv](https://docs.astral.sh/uv/), and a Discord application with a
bot token and a test server (your *dev guild*) where the bot is invited with the
`applications.commands` and `bot` scopes.

## 1. Project

```bash
uv init --package my-bot && cd my-bot
```

`pyproject.toml` (the core is a public repository, so the git dependency needs no
credentials; pin a **tag**):

```toml
[project]
name = "my-bot"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
    "discord-bot-core[sqlite] @ git+https://github.com/rubidium-labs/discord-bot-core.git@v0.1.0",
]

[project.scripts]
my-bot = "my_bot.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "ruff"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

(`[sqlite]` is only for a database; drop it for a bot without one.) Then `uv sync`, and commit
`uv.lock`. To upgrade the core later, change the tag and run `uv lock --upgrade-package
discord-bot-core`.

Layout (`src/` layout):

```
my-bot/
├── pyproject.toml  uv.lock  .env  .env.example  .gitignore   # .env is git-ignored
├── src/my_bot/
│   ├── __init__.py
│   ├── __main__.py        # composition root
│   ├── settings.py
│   ├── bot.py
│   └── cogs/
│       ├── __init__.py
│       └── hello.py
└── tests/
```

## 2. Settings

An app subclasses `CoreSettings` and adds its own fields. A field without a default is
required: the bot refuses to start without it.

```python
# src/my_bot/settings.py
from discord_bot_core.settings import CoreSettings


class AppSettings(CoreSettings):
    greeting: str          # required: env var GREETING
```

## 3. The bot

```python
# src/my_bot/bot.py
from discord_bot_core import CoreBot
from my_bot.settings import AppSettings


class MyBot(CoreBot):
    settings: AppSettings   # narrows the type for the cogs

    def __init__(self, settings: AppSettings) -> None:
        super().__init__(settings, extensions_package="my_bot.cogs")
```

`extensions_package` names the package where the extensions (cogs) are discovered. With no
cog the bot already runs and offers `/admin sync ...` and `/admin ext ...` in the dev guild.

## 4. A cog with one slash command

```python
# src/my_bot/cogs/hello.py
import discord
from discord import app_commands
from discord.ext import commands

from my_bot.bot import MyBot


class HelloCog(commands.Cog):
    def __init__(self, greeting: str) -> None:
        self._greeting = greeting

    @app_commands.command(name="hello", description="Say hello.")
    @app_commands.describe(name="Who to greet")
    async def hello(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.send_message(f"{self._greeting}, {name}!", ephemeral=True)


async def setup(bot: MyBot) -> None:
    await bot.add_cog(HelloCog(bot.settings.greeting))
```

Dependencies come in through the cog's constructor, from `setup()`. A cog never imports
a global bot. To use the database in a command, add `@transactional` under
`@app_commands.command` and read the session with `get_session(interaction)` (see
[design section 12](design.md#12-the-transactional-session-per-command)); it adds no
slash-command option.

## 5. Entry point

The composition root is the only place that builds objects:

```python
# src/my_bot/__main__.py
import asyncio
import sys

from my_bot.bot import MyBot
from my_bot.settings import AppSettings


async def sync_dev() -> None:
    """One-shot: publish the commands to the dev guild, without a gateway connection."""
    settings = AppSettings.load()
    bot = MyBot(settings)
    async with bot:
        await bot.login(settings.discord_token.get_secret_value())  # runs setup_hook, no websocket
        commands = await bot.sync_dev_guild()
    print(f"Synced {len(commands)} commands to the dev guild.")


def main() -> None:
    if sys.argv[1:] == ["sync-dev"]:
        asyncio.run(sync_dev())
        return
    MyBot(AppSettings.load()).launch()   # configures logging, then runs the bot


if __name__ == "__main__":
    main()
```

`AppSettings.load()` validates the settings and stops the process with a readable message
if one is missing.

## 6. Configuration for a local run

Create `.env` from `.env.example` (git-ignored) and fill the values in locally:

```
DISCORD_TOKEN=            # your dev application's bot token
DEV_GUILD_ID=             # id of your test server
ENVIRONMENT=dev
LOG_LEVEL=INFO
GREETING=                 # the app's own required setting
```

Every core setting is described in [configuration](configuration.md). On a platform that
mounts Docker secrets, `discord_token` is read from `/run/secrets/discord_token` instead.
Add `GREETING` (names only) to your app's `.env.example` too.

## 7. Run, and the first sync

```bash
uv run python -m my_bot sync-dev     # once, and after adding or changing commands
uv run python -m my_bot              # start the bot
```

The first sync is a one-shot you run on purpose: on a fresh application the `/admin`
commands do not exist in Discord yet, and they are what registers everything else
([design section 8](design.md#8-dev-guild-and-sync)). The bot never syncs by itself at
start (Discord rate-limits it). After that first run:

- In the dev guild, run `/admin sync dev`: in `dev` the app's commands are copied there
  and synced, so `/hello` shows up at once.
- For production (`ENVIRONMENT=prod`), `/admin sync global` publishes the global commands.
- `/admin ext load|unload|reload|list` manage the cogs without a restart; run
  `/admin sync dev` afterwards if the commands changed.

All `/admin` commands are owner-only (the application's owner or team, or `OWNER_IDS`) and
exist only in the dev guild.

## 8. Tests

```python
# tests/test_hello.py
from discord_bot_core.testing import FakeInteraction

from my_bot.cogs.hello import HelloCog


async def test_hello_greets_ephemeral() -> None:
    cog = HelloCog("Hi")
    interaction = FakeInteraction()
    await cog.hello.callback(cog, interaction, name="Ada")

    sent = interaction.response.sent[0]
    assert sent.content == "Hi, Ada!"
    assert sent.ephemeral is True
```

```bash
uv run pytest
uv run ruff check && uv run ruff format
```

More in [testing](testing.md).

## 9. If you use a database

Set `DATABASE_URL` (for SQLite, `sqlite+aiosqlite:///` plus a path on a volume) and write
models on the core's `Base`. The core never creates tables or runs migrations at start;
your app owns Alembic. The URL stays out of `alembic.ini` so a secret never lands in git;
`env.py` takes it from the same settings as the bot.

Minimal `alembic.ini`:

```ini
[alembic]
script_location = alembic
# sqlalchemy.url is deliberately not set: alembic/env.py reads it from AppSettings

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

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

Deploy by running `alembic upgrade head` as a separate step, then start the bot
([design section 11.1](design.md#111-alembic-pattern-for-apps)).

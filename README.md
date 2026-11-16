# discord-bot-core

The base every Rubidium Labs Discord bot is built on: a small, tested Python library on
top of [discord.py](https://discordpy.readthedocs.io/) 2.x. It has **no feature of its
own**. A bot that subclasses `CoreBot` and has no cog already starts and offers:

- validated settings (`CoreSettings`, pydantic-settings; secrets as `SecretStr`, from the
  environment, `.env` or secret files),
- a dev guild with owner-only admin commands: sync (global, dev guild, one guild) and
  extensions (load, unload, reload, list). Sync is never automatic,
- one error handler for all slash commands (user-facing errors, generic message with an
  error id, optional error-log channel, works in DMs),
- standard `logging`, configured once,
- optional async SQLAlchemy 2 database, Alembic support, and a transactional session per
  command (`@transactional`, `get_session`),
- a base for HTTP clients and a small UI kit (embeds, status message, views),
- fakes to test your bot without Discord (`discord_bot_core.testing`).

No singletons: everything is passed explicitly. Licence: [MIT](LICENSE).

> **Status:** implemented, pre-release. The architecture is in
> [docs/design.md](docs/design.md); all 13 implementation steps are merged on `main`.
> The first tagged release is `v0.1.0` (tag pushed by the maintainer).

## Quick start

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/). Add the library as a git
dependency on a tag in your `pyproject.toml`:

```toml
dependencies = [
    "discord-bot-core @ git+https://github.com/rubidium-labs/discord-bot-core.git@v0.1.0",
]
```

A minimal bot (package `my_bot`):

```python
# my_bot/settings.py
from discord_bot_core.settings import CoreSettings

class AppSettings(CoreSettings):
    """Add your own settings here; a field without a default is required."""

# my_bot/__main__.py
from discord_bot_core.bot import CoreBot
from my_bot.settings import AppSettings

class MyBot(CoreBot):
    pass

def main() -> None:
    settings = AppSettings.load()              # validated here, or the process stops
    MyBot(settings, extensions_package="my_bot.cogs").launch()

if __name__ == "__main__":
    main()
```

The full path, with a cog, the first command sync and tests, is in
[docs/getting-started.md](docs/getting-started.md).

## Run locally

```bash
cp .env.example .env        # then fill in DISCORD_TOKEN and DEV_GUILD_ID (names only in the example)
uv sync
uv run python -m my_bot
```

`.env` is read by the settings; it is git-ignored and never committed. Settings:
[docs/configuration.md](docs/configuration.md).

## Tests

```bash
uv sync
uv run pytest            # no Discord or network needed; reports coverage
uv run ruff check
uv run ruff format
```

Testing a bot built on the core: [docs/testing.md](docs/testing.md).

## Documentation

- [Design](docs/design.md): architecture, layers, decisions and their reasons
- [Getting started](docs/getting-started.md): from zero to a running bot with one cog
- [Configuration](docs/configuration.md): every setting
- [Dev guild and sync](docs/dev-guild-and-sync.md): where commands live, `/core sync`
- [Extensions](docs/extensions.md): discovery, `/core ext`, autocomplete
- [Database and sessions](docs/database.md): engine, Alembic, per-command transaction
- [Error handling](docs/error-handling.md): exception table, replies, error-log channel
- [UI kit](docs/ui-kit.md): embeds, status messages, views and modals
- [Testing](docs/testing.md): tests without Discord
- [Releasing](docs/releasing.md): how versions and tags are made
- [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

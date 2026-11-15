# discord-bot-core — design

Status: proposed (design PR). Target release: `v0.1.0`.
Audience: the maintainers, and whoever builds a bot on the library.

`discord-bot-core` is the base every Discord bot of Rubidium Labs starts from. It has
**no feature of its own**: a bot that subclasses `CoreBot` and has no cog must start
and offer the admin commands (sync, extensions), settings, error handling, logging, an
optional database and a small UI kit.

This page decides everything the brief left open, with the reason and the alternatives
that were rejected. Facts about discord.py were checked against the source of
`discord.py==2.7.1` (installed in a scratch virtualenv), not from memory; where a
decision rests on such a fact, it is marked **[verified]** and the place is named.

Companion pages: [getting-started](getting-started.md), [configuration](configuration.md),
[testing](testing.md). More pages are written together with the code, as the brief asks
(docs are part of each implementation PR): see [Documentation plan](#16-documentation-plan).

Contents: 1 Principles · 2 Dependencies · 3 Layout · 4 Dependency injection ·
5 Settings · 6 Logging · 7 The bot · 8 Dev guild and sync · 9 Extensions ·
10 Errors · 11 Database · 12 Per-command session · 13 Clients · 14 UI kit ·
15 Testing · 16 Documentation plan · 17 Implementation steps · 18 Risks ·
19 Open questions · 20 Traceability

---

## 1. Principles

1. **Explicit dependencies.** Nothing is reachable through a module-level global or a
   singleton. A thing that needs the settings, the database or a client gets it as a
   constructor argument. Importing the package creates no bot, engine or settings object
   (there is a test for it).
2. **Layers point one way.** `ui` and `commands` may use `errors`, `settings`,
   `infrastructure`; `infrastructure` imports no `discord`; business code of the app
   (services) imports neither `ui` nor, if avoidable, `discord`.
3. **Fail at start, not at 3 a.m.** Settings are validated when the bot object is built;
   a missing token or dev guild stops the process with a readable message.
4. **Never silently do rate-limited things.** Command sync is a command (or an explicit
   one-shot), never a side effect of starting.
5. **Secrets never reach a log, an embed or a repr.**
6. **Testable without Discord.** Every piece that talks to Discord does so through a
   narrow seam (an `Interaction`-shaped object, a `Protocol`), and the library ships
   fakes for those seams (`discord_bot_core.testing`).

## 2. Dependencies and version policy

| Package | Constraint (library) | Why |
|---|---|---|
| Python | `requires-python = ">=3.14"` | "Latest stable"; CI uses 3.14 (workflows `templates/project.yml`). |
| `discord.py` | `>=2.7.1,<3` | Latest on PyPI at design time is 2.7.1 (2026-03). Major 3 may break the app-commands API we subclass. |
| `pydantic-settings` | `>=2.10,<3` (floor confirmed by CI, see below) | `SecretStr`, `secrets_dir`, `_secrets_dir` init argument. Verified with 2.16.3. |
| `SQLAlchemy[asyncio]` | `>=2.0,<3` | 2.x async API (`async_sessionmaker`, `DeclarativeBase`). Verified with 2.1.8. |
| `alembic` | `>=1.13,<2` | Migrations for apps (section 11). |
| `aiosqlite` | optional extra `sqlite` | Dev and small deployments (SQLite file in a Docker volume). |
| `asyncpg` | optional extra `postgres` | Declared now so apps do not need a library change later. |

`aiohttp` is already a hard dependency of discord.py; the clients base uses it and the
library adds no new HTTP dependency.

Dev dependency group (`[dependency-groups] dev`, installed by `uv sync`): `pytest`,
`pytest-asyncio` (mode `auto`), `pytest-cov`, `ruff`, `mypy`.

**Version policy.**

- A library: lower bounds are the lowest versions CI proves to work, upper bounds stop at
  the next major. `uv.lock` is committed and pins what CI and contributors use.
- CI runs the suite twice: `uv run pytest` on the lock (the workflow template command),
  and a second job with `uv sync --resolution lowest-direct` to keep the floors honest.
  The floors above are therefore *provisional* until that job has run once.
- Dependabot/renovate style bumps of `uv.lock` are normal PRs (`chore(deps): ...`).
- Version of discord-bot-core: SemVer. While `0.x`, a minor release may break the public
  API (listed in `discord_bot_core.__all__` and the documented modules) and says so in
  the changelog under **Changed**/**Removed**.

**pytest-asyncio vs anyio**: pytest-asyncio chosen. discord.py and SQLAlchemy's async
layer are asyncio-only, anyio's backend matrix would test nothing real. Rejected: anyio.

**Type checking.** Type hints everywhere is a rule; a checker is *not* in the brief's CI
list. The package ships `py.typed`, and CI runs mypy alongside ruff and pytest
(review decision 4, §19); dev group adds `mypy`.

## 3. Package name and layout

Distribution name `discord-bot-core`, import name `discord_bot_core`. (Alternatives
rejected: `rubidium_core` — the library is generic and public, a Rubidium name would tie
it to one org; `discordbotcore` — unreadable.)

```
discord-bot-core/
├── pyproject.toml            # uv, hatchling backend, ruff + pytest config
├── uv.lock
├── README.md  CHANGELOG.md  CONTRIBUTING.md  LICENSE  .env.example
├── docs/
├── src/discord_bot_core/
│   ├── __init__.py           # public API re-exports, __version__ (importlib.metadata)
│   ├── py.typed
│   ├── logging_config.py     # configure_logging(level, environment)
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── core.py           # CoreSettings, Environment, LogLevel
│   │   └── loading.py        # DEFAULT_SECRETS_DIR, load helper
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── core_bot.py       # CoreBot
│   │   └── tree.py           # CoreCommandTree
│   ├── extensions/
│   │   ├── __init__.py
│   │   ├── discovery.py      # discover_extensions(package) -> list[str]  (pure)
│   │   └── manager.py        # ExtensionManager
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── checks.py         # owner_only, dev_guild_only, OwnerOnlyError
│   │   ├── transactional.py  # @transactional, get_session()
│   │   └── admin/
│   │       ├── __init__.py   # AdminCog (group "admin"), setup helper
│   │       ├── sync.py       # /core sync global | dev | guild
│   │       └── extensions.py # /core ext load | unload | reload | list
│   ├── errors/
│   │   ├── __init__.py
│   │   ├── exceptions.py     # CoreError, UserFacingError, ...
│   │   └── handler.py        # ErrorHandler, ErrorReport, classify()
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── database.py   # Database (engine + session factory + transaction())
│   │   │   ├── base.py       # Base (DeclarativeBase), NAMING_CONVENTION
│   │   │   ├── repository.py # BaseRepository
│   │   │   └── migrations.py # run_migrations() helper for an app's alembic/env.py
│   │   └── clients/
│   │       ├── __init__.py
│   │       └── base.py       # BaseHttpClient, ExternalServiceError
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── theme.py          # EmbedTheme, DEFAULT_THEME
│   │   ├── embeds.py         # info/success/warning/error embeds, truncate()
│   │   ├── status.py         # StatusMessage, StatusRenderer, MessageEditor
│   │   └── views.py          # BaseView, SingleUserView
│   └── testing/              # public helpers for tests of apps (no pytest import)
│       ├── __init__.py
│       ├── interactions.py   # FakeInteraction, FakeResponse, FakeFollowup
│       └── database.py       # memory_database()
└── tests/                    # mirrors src/ one-to-one, plus tests/integration/
```

Notes on the layout:

- `commands/` is the Discord-facing layer for things the *core* offers (admin commands,
  the `transactional` decorator, checks). It is not where an app's commands go.
- `infrastructure/` follows the brief and the layout of rubidium-bot, so both repos read
  the same. `infrastructure/database` and `infrastructure/clients` import no `discord`.
- `testing/` ships in the wheel on purpose (see section 15).
- Hatchling is the build backend (plain, supports `src/`, git dependencies work with
  `uv`/pip). Rejected: `uv_build` (younger, would make git-dependency installs by pip
  depend on it too) — can be revisited.

## 4. Class names and dependency injection

| Class | Module | Role |
|---|---|---|
| `CoreSettings` | `settings.core` | pydantic-settings model; apps subclass it. |
| `Environment` | `settings.core` | `StrEnum`: `DEV = "dev"`, `PROD = "prod"`. |
| `CoreBot` | `bot.core_bot` | `commands.Bot` subclass; the composition root's main object. |
| `CoreCommandTree` | `bot.tree` | `app_commands.CommandTree` subclass: `on_error`, `interaction_check` (logging). |
| `ExtensionManager` | `extensions.manager` | load/unload/reload/list over a *named package*. |
| `ErrorHandler` | `errors.handler` | turns an exception into (user message, log record, channel report). |
| `UserFacingError` | `errors.exceptions` | the domain exception carrying a user message. |
| `Database` | `infrastructure.database.database` | engine + `async_sessionmaker` + `transaction()`. |
| `Base` | `infrastructure.database.base` | the declarative base apps' models derive from. |
| `BaseRepository` | `infrastructure.database.repository` | holds the `AsyncSession` given at construction. |
| `StatusMessage` | `ui.status` | the one-message-edited-at-each-step helper. |
| `BaseView`, `SingleUserView` | `ui.views` | view base classes. |
| `EmbedTheme` | `ui.theme` | colours/footer for the embed helpers. |

### 4.1 How things are passed

The **composition root** is the app's `__main__`/`main()`. It is the only place that
creates objects and wires them:

```python
settings = AppSettings.load()                 # validated here, or the process stops
bot = RubidiumBot(settings)                   # CoreBot subclass
bot.launch()                                  # configures logging, runs
```

- `CoreBot.__init__(settings, *, extensions_package=None, database=None,
  error_handler=None, intents=None, **options)`. Everything has a seam: a test passes its
  own `database` (in-memory SQLite) or `error_handler`. Production code passes nothing and
  the bot builds the defaults from `settings`.
- The bot exposes what it owns as **read-only attributes**: `bot.settings`,
  `bot.database` (`Database | None`), `bot.extension_manager`, `bot.error_handler`.
  discord.py hands the bot to every cog and as `interaction.client`; that is the only
  "service locator" and it is not global.
- **Cogs** get their dependencies in their constructor, from the extension's `setup()`:

  ```python
  async def setup(bot: RubidiumBot) -> None:
      await bot.add_cog(SecretSantaCog(settings=bot.settings, clock=SystemClock()))
  ```
- **Services** never see the bot. They take repositories/clients/functions they need.
  The cog (thin) builds the per-command object graph from the command's session (12.4).
- **App-level shared objects** (an HTTP client, a cache) are created in the app's bot
  subclass in an overridable async hook `CoreBot.configure()` (called by `setup_hook`
  after the database exists and before extensions load) and stored on the bot subclass.
  Resources that need closing are registered with `bot.register_cleanup(coro_fn)`;
  `CoreBot.close()` runs them (LIFO) then disposes the database.
- A cog never imports "the bot" module; it only annotates `setup(bot: RubidiumBot)`.

**Rejected:** a `SingletonMeta`/module-level `bot` (the brief's flaw list); a DI
container library (`dependency-injector`, ...): for a handful of objects, wiring in the
composition root is shorter, type-checks, and teaches nothing new to contributors; a
contextvar holding "the current bot" (hidden dependency again).

## 5. Settings

`CoreSettings(pydantic_settings.BaseSettings)`. Names map to environment variables
case-insensitively (`discord_token` ← `DISCORD_TOKEN`) and, for secrets, to a file of the
same name in the secrets directory.

| Field | Type | Required | Secret |
|---|---|---|---|
| `discord_token` | `SecretStr` | **yes** (no default) | **yes** |
| `dev_guild_id` | `PositiveInt` | **yes** (no default) | no |
| `environment` | `Environment` (`dev`/`prod`) | no, default `prod` | no |
| `log_level` | `Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` | no, default `INFO` | no |
| `error_log_channel_id` | `PositiveInt \| None` | no, default `None` (feature off) | no |
| `database_url` | `SecretStr \| None` | no, default `None` (bot runs without database) | **yes** (may embed a password) |

Full text and sources: [configuration](configuration.md).

Decisions:

- **No default for the token and the dev guild; no hard-coded id anywhere in the
  library.** Missing → `pydantic.ValidationError` at `CoreSettings.load()`, which the
  `launch()` wrapper catches to print one line per bad field (field name only, never the
  value) and exit with status 2.
- **`environment` defaults to `prod`.** The safe side: dev behaviour (copy commands to the
  dev guild) must be asked for. Since sync is never automatic, a wrong default cannot
  publish anything by itself.
- **`database_url` is a `SecretStr`** because URLs carry passwords. The core calls
  `.get_secret_value()` in exactly two places (`Database.__init__`, the alembic helper).
- **Owner check:** discord.py's `Bot.is_owner` falls back to the application's
  owner/team when no `owner_ids` are given **[verified: `ext/commands/bot.py`
  `is_owner`, `owner_ids` option]** — the core sets no `owner_ids`, so "owner only" means
  the application's owner or team.
- **Sources and priority** (pydantic-settings, **[verified by experiment]**): init
  arguments > environment > `.env` file > secrets directory. So an environment variable
  overrides a secrets file, and a secrets file is the fallback.
- **`secrets_dir`**: pydantic-settings warns (`UserWarning: directory ... does not exist`)
  when a configured `secrets_dir` is missing **[verified]**. To avoid that noise on a dev
  machine, `model_config` does *not* hard-code it. `CoreSettings.load(secrets_dir=
  DEFAULT_SECRETS_DIR)` passes `_secrets_dir=` only if the directory exists.
  `DEFAULT_SECRETS_DIR = Path("/run/secrets")` (Docker/Compose secrets; one file per
  secret, name = field name, trailing newline stripped by pydantic-settings
  **[verified]**). Tests build `CoreSettings(discord_token=..., dev_guild_id=...)`
  directly and never read the environment (`_env_file=None`).
- **`.env`**: `model_config` sets `env_file=".env"`; pydantic-settings reads it itself and
  does **not** copy it into `os.environ`. There is no `load_dotenv` and no `os.getenv`
  in the library, so there is one source of truth. `.env.example` lists names only.
- `extra="ignore"` (an app's environment contains unrelated variables);
  `frozen=True` (settings do not change at runtime).
- **Never logged.** `SecretStr` masks `repr`/`str`/`model_dump`. The startup log line is
  produced by `CoreSettings.describe()` which returns a dict of the non-secret fields
  plus `database: configured|not configured`; the URL (even redacted) is not printed.
  SQLAlchemy `echo` is not exposed as a setting (it logs bound parameters).
- Apps extend by subclassing (`class AppSettings(CoreSettings): ...`). `CoreBot` accepts
  any `CoreSettings` subclass; the app's bot subclass narrows the attribute type
  (`settings: AppSettings`). Making `CoreBot` generic over the settings type was rejected
  as noise for one annotation.

**Rejected:** `pydantic.SecretStr` for ids (not secret); one `.env` + `python-dotenv`
(the brief's flaw); an `owner_ids` env var (the application owner/team is the default).

## 6. Logging

`logging_config.configure_logging(level: str, environment: Environment) -> None`,
called once, from `CoreBot.launch()` before the client starts.

- Standard library `logging` only. One `StreamHandler(sys.stderr)` on the root logger,
  tagged so a second call replaces it instead of stacking handlers (idempotent; tests
  can call it freely and `caplog` keeps working because pytest's handler is not touched).
- Format: `%(asctime)s %(levelname)-8s %(name)s: %(message)s`. Colour: none (container
  logs). Dev may use a plainer format; it is the same code path.
- Level from `settings.log_level`; applied to the root logger. The `discord` loggers are
  not special-cased (a `DEBUG` run is verbose, and that is what DEBUG is for; the
  gateway logger at DEBUG can print payloads, so DEBUG is not for production — said in
  the configuration page).
- discord.py configures its own handler in `Client.run()` unless `log_handler=None`
  **[verified: `client.py` `run(..., log_handler=MISSING)`]**; `launch()` passes
  `log_handler=None` so there is exactly one configuration.
- The library's own loggers are `logging.getLogger(__name__)`. **Log calls use lazy
  `%s` arguments, never f-strings** (ruff rule `G004` enforces it), no bare `except`,
  `raise` not `raise e`.
- `CoreCommandTree.interaction_check` logs one INFO line per command invocation:
  qualified name, user id, guild id (`None` in DMs). **Command options are never logged**
  (a Secret Santa participant list is personal data).

## 7. The bot

```python
class CoreBot(commands.Bot):
    def __init__(self, settings: CoreSettings, *, extensions_package: str | None = None,
                 database: Database | None = None, error_handler: ErrorHandler | None = None,
                 intents: discord.Intents | None = None, **options: Any) -> None: ...
    settings: CoreSettings
    database: Database | None
    extension_manager: ExtensionManager
    error_handler: ErrorHandler

    async def setup_hook(self) -> None: ...        # see below
    async def configure(self) -> None: ...         # override point for the app
    def register_cleanup(self, fn: Callable[[], Awaitable[None]]) -> None: ...
    async def sync_global(self) -> list[AppCommand]: ...
    async def sync_dev_guild(self) -> list[AppCommand]: ...
    async def sync_guild(self, guild_id: int) -> list[AppCommand]: ...
    def launch(self) -> None: ...                   # configure_logging + run(log_handler=None)
    async def sync_dev_guild_once(self) -> list[AppCommand]: ...   # one-shot, no gateway
    async def close(self) -> None: ...             # cleanups, database.dispose(), super
```

- Built with `tree_cls=CoreCommandTree`, `command_prefix` unused (`commands.when_mentioned`;
  there are no prefix commands), `intents=discord.Intents.default()` unless given.
  Privileged intents (`members`, `message_content`) are the app's explicit choice; the
  core needs none and defaults to `Intents.default()` (§19 decision 6).
- **`setup_hook`** (runs once, before the gateway connects **[verified: `Client.login`
  calls `setup_hook` after `static_login`]**): 1. start the database (engine creation is
  lazy, no I/O; log "database configured" or "no database"); 2. `await self.configure()`;
  3. add the core cog (`/core` group) scoped to the dev guild (section 8); 4. load all discovered
  extensions if `extensions_package` was given (`auto_load` can be turned off);
  a failing extension is logged with traceback and the bot continues (an admin can fix and
  `/core ext reload`), unless `strict_extensions=True`.
- **No `on_ready` handler in the core.** (`on_ready` fires on every reconnect; Glow synced
  and spoke there.) Nothing is sent to any channel at start.
- `CoreBot.launch()` is the happy path: configure logging, `self.run(token,
  log_handler=None)`. Using `async with bot: await bot.start(token)` stays possible.
- No global message-content or prefix behaviour: the base is slash-command only.

## 8. Dev guild and sync

**Where commands live.**

- Commands of cogs (global `app_commands`) are registered in the tree as *global*.
- The core's cog (group `/core`) is added with `add_cog(cog, guild=Object(dev_guild_id))`
  **[verified: `Bot.add_cog(..., guild=, guilds=)`]**, so `/core ...` exists *only in the
  dev guild*, in dev and in prod alike. The groups are `guild_only` (`/core` is not
  available in DMs) and have the `owner_only` check.
- In **prod** nothing is copied. Global commands are published by `/core sync global`.
- In **dev** (`environment == "dev"`), the app's commands are *copied* into the dev guild
  and synced there, so changes show up instantly and nothing leaks to other guilds.

**The sync commands** (all owner-only, dev guild only):

| Command | Behaviour |
|---|---|
| `/core sync global` | `tree.sync()` — publishes the global commands. The `/core` group is guild-scoped, so it is not part of it. In dev the reply adds "environment is dev; global commands are normally not published here". Allowed, never blocked. |
| `/core sync dev` | prod: `tree.sync(guild=dev)` (admin commands only). dev: *reset, copy, sync* (below). |
| `/core sync guild <guild_id>` | `tree.sync(guild=Object(id))`: guild-scoped commands of that guild (none by default; for apps that register per-guild commands). Replies with count. A text option `guild_id` (Discord integers overflow in options, so it is a string parsed to `int`; bad input → `UserFacingError`). |

**Dev "reset, copy, sync"** (`CoreBot.sync_dev_guild`): `copy_global_to` *overrides* same
name commands but never removes commands that left the global tree (an unloaded cog),
**[verified: `tree.py` `copy_global_to` doc "will override pre-existing guild commands"]**,
so the dev guild would keep stale commands. Therefore: remove every command from
the dev guild's tree except the `/core` group object, call
`tree.copy_global_to(guild=dev)`, then `tree.sync(guild=dev)`. It is idempotent and runs on
every `/core sync dev`, so it is also correct after `/core ext reload`. The 100-command
limit surfaces as `CommandLimitReached` → generic error path.

Each sync reply is an ephemeral embed: scope, number of commands, names (truncated).
Sync results are logged at INFO (scope, count, user id).

**Sync is only a command.** Never in `setup_hook`, never in `on_ready`.

**First start (bootstrap).** On a fresh application the admin commands are not registered
yet, and they are what registers things. Without a way out, the very first sync would need
a REPL. Decision: `CoreBot.sync_dev_guild_once()`, an explicit *one-shot*:

```python
async def sync_once() -> None:
    bot = RubidiumBot(AppSettings.load())
    async with bot:
        await bot.login(token)          # no gateway; login sets application_id and runs setup_hook
        await bot.sync_dev_guild()
```

**[verified: `Client.login` fetches `application_info`, sets `application_id`, then calls
`setup_hook`; no websocket is opened.]** The app exposes it as `python -m rubidium_bot
sync-dev` (the getting-started page shows the 10 lines). It syncs the **dev guild only**,
it is run by a human on purpose, and it is never part of a normal start. This is the one
place where the design reads the brief's "sync is a command" broadly (a CLI command);
it is listed in open questions (19).

**Rejected:** syncing in `on_ready`/`setup_hook` when "commands changed" (needs a hash
store; still automatic); a hidden prefix command (`!sync`) as the bootstrap (needs the
message-content intent, which the base avoids); a dev-guild admin command per app
(duplicates the core).

## 9. Extensions

**Discovery** (`extensions/discovery.py`, pure and testable):
`discover_extensions(package: str) -> list[str]` imports the package (`importlib.
import_module`), iterates `pkgutil.iter_modules(package.__path__)`, skips names starting
with `_` and sub-packages without `setup`... (packages are included when they are
packages with an `__init__` defining `setup`; checked lazily by load, not by import, to
avoid executing every module at discovery), returns sorted fully-qualified names
(`rubidium_bot.cogs.secret_santa`). The app names the package once: 
`CoreBot(settings, extensions_package="rubidium_bot.cogs")`. Rejected: globbing `*cog.py`
on a relative filesystem path (Glow: depends on the working directory; and its
`get_extension_path` called `.join` on a list); a config setting for the package (code, not
configuration).

**`ExtensionManager(bot, package)`**:

```python
def available(self) -> list[str]            # discovered
def loaded(self) -> list[str]               # discovered ∩ bot.extensions
def unloaded(self) -> list[str]
async def load(self, name: str) -> None
async def unload(self, name: str) -> None
async def reload(self, name: str) -> None
async def load_all(self) -> LoadReport      # per-name success/failure
def resolve(self, short_or_full: str) -> str   # "secret_santa" -> full name; unknown -> UserFacingError
```

- It only manages names *inside the named package*: an owner cannot `load` an arbitrary
  importable module (`os`, `anything.else`) through the command. That is a security
  property, tested.
- discord.py already raises `ExtensionAlreadyLoaded`/`ExtensionNotLoaded`/
  `ExtensionNotFound`/`ExtensionFailed`/`NoEntryPointError`
  **[verified: `ext/commands/errors.py`]**; the manager maps them to `UserFacingError`
  with a plain message (the module name, not a traceback). `ExtensionFailed` also logs the
  traceback (WARNING with `exc_info`).
- `bot.load_extension` is a coroutine in 2.x **[verified]**; the manager awaits it. The
  core does not override `Bot.load_extension` (Glow did, with a try/except
  `AttributeError` that hid bugs).
- After load/unload/reload of an extension that defines app commands, the tree is
  *dirty*; the reply says "run `/core sync dev`" — it does not sync on its own.

**Core extension commands** (`/core ext ...`, owner only, dev guild):

| Command | Option | Autocomplete offers |
|---|---|---|
| `/core ext load` | `name` | unloaded extensions |
| `/core ext unload` | `name` | loaded extensions |
| `/core ext reload` | `name` | loaded extensions |
| `/core ext list` | — | — (embed: loaded ✅ / available ⬜) |

Autocomplete: `app_commands.autocomplete(name=...)` **[verified: `commands.py`
`autocomplete(**parameters)`]** returning ≤ 25 `Choice`s, filtered by the typed prefix/
substring. Choice `name` is the short module name, `value` the full name. discord.py
swallows autocomplete exceptions and only logs them **[verified: `tree.py` `_call`,
"Suppress exception since it can't be handled anyway"]**, and autocomplete does not run the
command checks; so each autocomplete callback re-checks `owner_only` itself and returns
`[]` for non-owners (they must not see extension names).

## 10. Error handling

One `on_error` on `CoreCommandTree`, delegating to `ErrorHandler`:

```python
class CoreCommandTree(app_commands.CommandTree[CoreBot]):
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError, /) -> None:
        await self.client.error_handler.handle(interaction, error)
```

**[verified]** signature: `async def on_error(self, interaction, error, /)` in 2.7.1
(`tree.py`; the positional-only `/` matters for overrides). The tree invokes it only
for `AppCommandError`s; a callback exception arrives wrapped in `CommandInvokeError`
with `.original` **[verified: `errors.py`]**. A failed `interaction_check` returns without
calling `on_error`, so `CoreCommandTree.interaction_check` never raises for checks
that should be user-visible (the owner check is a command check, not a tree check).

**`ErrorHandler.handle` algorithm**

1. `original = error.original if isinstance(error, CommandInvokeError) else error`.
2. Classify (`classify(original) -> Outcome`):

   | Exception | User sees (ephemeral) | Log |
   |---|---|---|
   | `UserFacingError` (or subclass) | its `.message` | INFO, no traceback |
   | `OwnerOnlyError`, `app_commands.CheckFailure` | "You can't use this command." | INFO |
   | `NoPrivateMessage` | "This command only works in a server." | INFO |
   | `MissingPermissions`, `BotMissingPermissions` | permissions named | INFO |
   | `CommandOnCooldown` | "Try again in N s." | INFO |
   | `CommandNotFound`, `CommandSignatureMismatch` | "This command is out of date, try again in a few minutes." | WARNING (means unsynced commands) |
   | `TransformerError` | "Invalid value for `option`." | INFO |
   | anything else | "Something went wrong. Error id: `ab12cd34`." | **ERROR with traceback** + report |

3. Unexpected path: `error_id = secrets.token_hex(4)` (8 hex chars, short enough to read
   aloud, collision-safe for the volume of one bot). Log
   `logger.error("Unhandled error %s in /%s user=%s guild=%s channel=%s", error_id, name,
   user_id, guild_id, channel_id, exc_info=original, extra={"error_id": error_id})`.
   `name = interaction.command.qualified_name if interaction.command else "<unknown>"`;
   `guild_id = interaction.guild_id` (an `int | None`, `None` in DMs) —
   **no `interaction.guild.name`/`.guild.id` anywhere in the core**; options values are
   not logged.
4. Reply: if `interaction.response.is_done()` → `followup.send(msg, ephemeral=True)`,
   else `response.send_message(msg, ephemeral=True)`. Reply failures
   (`discord.HTTPException`, expired token) are caught and logged; the handler itself
   never raises (an exception in `on_error` would only be logged by discord.py).
   Caveat, documented: if the command did `defer()` *non-ephemeral*, the first followup
   replaces the "thinking…" message and inherits its visibility; commands whose errors may
   be sensitive should `defer(ephemeral=True)` (the status message helper does).
5. Optional error-log channel (`error_log_channel_id`, unexpected path only): an embed with
   error id, command, user id, guild id (or "DM"), exception class and the **location**
   (`file:line` of the last frame) — *not* the exception message and not the full
   traceback (messages can contain personal data; the full traceback is in the log, found
   by error id). Sent with `bot.get_channel` falling back to `fetch_channel`; failures are
   logged and swallowed. At most one report per `(command, exception class)` per 60 s
   (injectable clock) to avoid flooding the channel when a command loops; suppressed
   count is added to the next report.
6. Secret Santa rule, generalised: exception messages of *unexpected* errors are only in
   the log, not shown to users or posted; domain code must not put sensitive data in
   `UserFacingError.message` (it is shown to the user who triggered it, which is fine, but
   it is also logged at INFO — so only for non-sensitive text).

**Domain exceptions** (`errors/exceptions.py`):

```python
class CoreError(Exception): ...                          # base of everything the core raises
class UserFacingError(CoreError):
    def __init__(self, message: str) -> None: ...        # .message, str(self) == message
class DatabaseNotConfiguredError(CoreError): ...          # programmer/config error, generic message + id
class NoActiveSessionError(CoreError): ...                # get_session() without @transactional
class ExternalServiceError(CoreError): ...                # clients layer
```

Apps define their own `class NotEnoughParticipants(UserFacingError)` etc. A service
raises it without importing discord.py; the tree turns it into the message. `commands`'s
checks raise `OwnerOnlyError` (subclass of `app_commands.CheckFailure`, so the generic
rules apply even without special handling).

**Errors in views and modals** do not reach the tree (discord.py calls `View.on_error`
**[verified: `ui/view.py:568`]** / `Modal.on_error` **[verified: `ui/modal.py:159`]**).
`BaseView.on_error` and `BaseModal.on_error` call the same `bot.error_handler.handle`,
so the behaviour is identical. Autocomplete errors cannot be answered (discord.py logs and
drops them), so autocomplete code must not raise.

**Order with the session**: the `@transactional` wrapper (12) rolls back and closes *before*
the exception reaches the tree, so the error reply never races an open transaction.

**Rejected:** per-command `@error` handlers as the main mechanism (scattered; they remain
available for special cases and run first, discord.py's `_has_any_error_handlers` rule is
untouched); a `try/except Exception` inside every cog method; ignoring `CheckFailure`
silently (a user must be told why nothing happened); sending tracebacks to Discord.

## 11. Database infrastructure

`infrastructure/database/`, no `discord` import.

```python
class Database:
    def __init__(self, url: str | SecretStr, *, pool_pre_ping: bool = True) -> None: ...
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]   # expire_on_commit=False
    def transaction(self) -> AbstractAsyncContextManager[AsyncSession]: ...
    async def ping(self) -> None: ...
    async def dispose(self) -> None: ...
```

- `create_async_engine(url, pool_pre_ping=True)`; `async_sessionmaker(engine,
  expire_on_commit=False, autoflush=True)`. `expire_on_commit=False` is deliberate: after
  commit the cog still reads result objects to build the reply, and an async session
  cannot lazy-load an expired attribute (it raises `MissingGreenlet`).
- SQLite specifics, applied only when the URL starts with `sqlite`: `PRAGMA
  foreign_keys=ON` on connect (SQLite ignores FKs otherwise); `:memory:` URLs get
  `StaticPool` + `check_same_thread=False` so every session sees the same database (this
  is what `testing.memory_database()` uses).
- `transaction()` is the **only** place that decides commit/rollback/close:

  ```python
  @asynccontextmanager
  async def transaction(self) -> AsyncIterator[AsyncSession]:
      session = self.session_factory()
      try:
          yield session
          await session.commit()            # success path only
      except BaseException:
          await asyncio.shield(session.rollback())
          raise
      finally:
          await asyncio.shield(session.close())
  ```
  `BaseException` so task cancellation (a command killed by shutdown) also rolls back;
  `shield` so the clean-up is not itself cancelled half way (the SQLAlchemy asyncio docs
  recommend this for `close`). The commit is *not* in `finally` — that is exactly the
  Glow/DSB bug (commit after rollback).
- `Base(DeclarativeBase)` with `metadata = MetaData(naming_convention=NAMING_CONVENTION)`
  (`ix`, `uq`, `ck`, `fk`, `pk` templates). Constraint names are deterministic, which
  Alembic needs to drop/alter constraints, in particular with SQLite batch mode. Apps
  write `class Draw(Base): __tablename__ = ...` and their migrations use `Base.metadata`.
  `Base` is a class, not state; the library defines no table, so there is nothing to
  collide. There is **no soft-delete mixin** in the core (DSB's `deleted_at is None` bug
  is a reason not to ship one before there is a need; a future mixin must use
  `.is_(None)` and have a test).
- `BaseRepository`: `__init__(self, session: AsyncSession)`, stores `self._session`;
  nothing else (no generic CRUD: it would hide the queries; apps write explicit
  repositories). Repositories never commit; they `add`/`flush`/`execute`.
- **Optional**: `CoreBot` builds a `Database` only if `settings.database_url` is set;
  otherwise `bot.database is None` and nothing imports a driver. Using
  `@transactional` on such a bot raises `DatabaseNotConfiguredError` at the first
  invocation (not at import) with a message naming the setting. A bot with no database
  never loads aiosqlite.
- **Never at start:** the core does not create tables and does not run migrations. (The
  app's deploy runs `alembic upgrade head` as a separate step before the bot; see below.)

### 11.1 Alembic pattern for apps

The app owns `alembic.ini`, `alembic/`, and its models. The core owns the wiring helper
so every app's `env.py` is five lines and uses the *same* settings (and secrets files) as
the bot:

```python
# alembic/env.py (app)
from alembic import context
from discord_bot_core.infrastructure.database import Base
from discord_bot_core.infrastructure.database.migrations import run_migrations
from rubidium_bot.settings import AppSettings
from rubidium_bot.infrastructure.database import models  # noqa: F401  (registers tables on Base.metadata)

settings = AppSettings.load()
run_migrations(context, metadata=Base.metadata, url=settings.database_url)
```

`run_migrations(context, *, metadata, url)`:

- URL missing → `DatabaseNotConfiguredError` with the setting name (no traceback noise).
- Offline mode: `context.configure(url=..., literal_binds=True)`.
- Online mode: the standard async recipe (`create_async_engine(..., poolclass=NullPool)`,
  `connection.run_sync(do_run_migrations)`), run with `asyncio.run`.
- `render_as_batch=True` when the dialect is SQLite (ALTER limitations),
  `compare_type=True`, `compare_server_default=True`.
- The URL is not put in `alembic.ini` (`sqlalchemy.url` stays empty/commented), so a
  secret never lands in a file in git.

Deploy sequence for an app: `alembic upgrade head` (one-off container command, same image,
same `/run/secrets`), then start the bot. The getting-started page includes a minimal
`alembic.ini`.

**Rejected:** a shared `Base` per app created by a factory (`make_base()`; more ceremony,
no gain); migrations at bot start (races with several replicas, hides failures, brief says
nothing runs implicitly); `sqlalchemy.url` in `alembic.ini` (secrets in git);
sync engine for Alembic (a second driver to install and configure).

## 12. The transactional session per command

This is the central design point.

### 12.1 The constraint (what discord.py 2.7.1 does)

**[verified: `app_commands/commands.py` `_extract_parameters_from_callback`]**

- `inspect.signature(callback)` is read; the first parameter (two inside a class: `self`,
  then `interaction`) is skipped; **every other parameter becomes a slash-command option**,
  and each one must be annotated or `TypeError` is raised; an annotation discord.py cannot
  map (`AsyncSession`) raises `TypeError: unsupported type annotation`.
- `inspect.signature` follows `functools.wraps`' `__wrapped__`, so a naive decorator that
  adds a parameter would add an option, and a decorator that *hides* it is only safe if
  the signature is controlled.
- String annotations (`from __future__ import annotations`) are resolved against
  `callback.__globals__` — the **wrapper's** module globals, not the user's
  **[verified by experiment]**: a plain `functools.wraps` wrapper defined in the library
  fails with `NameError: name 'app_commands' is not defined` for a cog module using
  postponed annotations, while a wrapper whose `__signature__` was computed with
  `inspect.signature(func, eval_str=True)` works.
- At call time discord.py does `callback(self.binding, interaction, **params)` (or
  without `binding`) **[verified: `Command._do_call`]**: the interaction is always the
  **last positional argument**, parameters are keywords.
- Exceptions from the callback are wrapped in `CommandInvokeError` and sent to
  `tree.on_error`; `CancelledError` (a `BaseException`) passes through unwrapped.

### 12.2 The mechanism: decorator + accessor on the interaction

Chosen: **an injected parameter is not used. The command gets its session from an
accessor that reads `interaction.extras`.**

```python
from discord_bot_core.commands import transactional, get_session

class SecretSantaCog(commands.Cog):
    @app_commands.command(name="secret-santa", description="Draw names.")
    @app_commands.describe(participants="Mentions of the participants")
    @transactional
    async def secret_santa(self, interaction: discord.Interaction, participants: str) -> None:
        session = get_session(interaction)                       # the command's one session
        service = SantaService(SantaRepository(session), AuditRepository(session))
        ...
```

Order of decorators: `@app_commands.command` outermost (it receives the wrapper),
`@transactional` directly above the `def` (or anywhere under `@app_commands.command`).
`@app_commands.describe/choices/rename/autocomplete/checks.*` work above or below it
because `functools.wraps` copies the function `__dict__` where those store their data
**[verified: they store `__discord_app_commands_*` attributes on the function]**.

**`transactional(func)`** (in `commands/transactional.py`):

1. `sig = inspect.signature(func, eval_str=True)` at decoration time; on `NameError`
   (forward reference to something not yet defined, e.g. under `TYPE_CHECKING`) fall back
   to the unevaluated signature and let discord.py resolve it as it does for any
   command.
2. `@functools.wraps(func)` async `wrapper(*args, **kwargs)`:

   ```python
   interaction = args[-1]                                  # last positional arg, see 12.1
   database = interaction.client.database                  # CoreBot attribute
   if database is None: raise DatabaseNotConfiguredError(...)
   async with database.transaction() as session:           # commit / rollback / close (11)
       interaction.extras[SESSION_KEY] = session
       try:
           return await func(*args, **kwargs)
       finally:
           interaction.extras.pop(SESSION_KEY, None)
   ```
3. `wrapper.__signature__ = sig` — so `inspect.signature(wrapper)` is *exactly* the
   original signature, which contains no session parameter, so **no option is added,
   provably**: the decorator does not change the signature at all, and it is verified by
   a test that builds a real `app_commands.Command` and asserts `[p.name for p in
   command.parameters]` (12.5).
4. If `func` is not a coroutine function → `TypeError` at decoration time.

**`get_session(interaction) -> AsyncSession`** returns `interaction.extras[SESSION_KEY]`
(`interaction.extras` is a plain `dict` on `discord.Interaction`
**[verified: `interactions.py` `self.extras: Dict[Any, Any] = {}`]**, new for each
interaction, so concurrent commands cannot see each other's session). Missing →
`NoActiveSessionError("get_session() called outside a @transactional command")`.
A `SESSION_KEY` is a private sentinel object, not a string, so an app cannot collide with it.

Why this answers the brief's constraints:

- *One session for the whole command:* created before the body, same object for every
  `get_session` call.
- *Commit on success, rollback on exception, close:* `Database.transaction()` (11).
- *Repositories/services don't open their own:* they take the session in their constructor.
- *Not an option:* signature untouched.
- *No hidden global:* no contextvar and no module state; the state lives on the
  interaction object that already scopes the command. A test passes a `FakeInteraction`
  with an `extras` dict.

### 12.3 Early commit

The body may need the data to be durable *before* it tells the user it is done (Secret
Santa: record, then post "finished"; or the reverse risk: "finished" shown, then the final
commit fails). Rule, documented: **commit before the final user-facing message**:

```python
await session.commit()      # explicit; the session remains usable (a new transaction begins)
await status.finish(...)
```

`expire_on_commit=False` makes this safe. If the final commit still fails, the exception
goes to the tree's error path: the user gets an ephemeral "Something went wrong, error id".
A long transaction (DMs between begin and commit) holds a SQLite write lock only from the
first write; keep slow Discord I/O *between* the reads and the single write block when the
database is SQLite.

### 12.4 How repositories and services receive the session

```python
class SantaRepository(BaseRepository):            # holds self._session
    async def add_draw(self, draw: Draw) -> None:
        self._session.add(draw); await self._session.flush()
```

The cog (thin) builds the object graph per command from the session; long-lived
dependencies come from the cog's constructor:

```python
class SecretSantaCog(commands.Cog):
    def __init__(self, settings: AppSettings) -> None: self._settings = settings
    ...
    session = get_session(interaction)
    service = SantaService(repo=SantaRepository(session), audit=AuditRepository(session), rng=SystemRandom())
```

Two repositories built from the same `get_session` result share the transaction; neither
commits. Alternatives rejected below.

### 12.5 Tests (all without Discord; see also [testing](testing.md))

Fixtures: `memory_database()` (in-memory SQLite, `StaticPool`, creates a tiny test table
via a test-local `Base` subclass), `FakeInteraction(client=FakeClient(database=db))`.

| Test | Asserts |
|---|---|
| `test_commit_on_success` | command adds a row through a repository, returns normally; a *new* session sees the row; the session passed to the body is closed afterwards. |
| `test_rollback_on_exception` | body adds a row then raises `RuntimeError`; the exception propagates unchanged; a new session sees no row; session closed. |
| `test_rollback_on_user_facing_error` | same with `UserFacingError`: still rolls back (domain errors are failures). |
| `test_no_commit_after_rollback` | a spy session records calls: `rollback` then `close`, never `commit`. (The Glow/DSB bug.) |
| `test_two_repositories_one_transaction` | repos A and B built from `get_session`: `A._session is B._session`; success → both rows visible; body raises after both inserts → neither visible. |
| `test_partial_progress_with_early_commit` | explicit `await session.commit()` then exception: first write persists, writes after it do not. |
| `test_session_not_an_option` | `@app_commands.command` over a `@transactional` method in a cog class: `[p.name for p in cmd.parameters] == ["participants"]`, also for a module using `from __future__ import annotations` (regression for the `__globals__` fact), also for `describe`-decorated params and for a free function. |
| `test_signature_is_unchanged` | `inspect.signature(wrapped) == inspect.signature(original, eval_str=True)`. |
| `test_get_session_outside_transaction` | `NoActiveSessionError`. |
| `test_database_not_configured` | `database=None` → `DatabaseNotConfiguredError` naming `database_url`; the body never ran. |
| `test_cancellation_rolls_back` | cancel the task while the body awaits; row absent; session closed; `CancelledError` propagates. |
| `test_extras_cleaned` | `SESSION_KEY` not in `interaction.extras` after success and after failure. |
| `test_concurrent_commands_distinct_sessions` | two commands run with `asyncio.gather`: sessions differ; one failing does not roll back the other. |
| `test_commit_failure_propagates` | spy session whose `commit` raises: exception propagates, rollback attempted, close called. |
| `test_error_path_end_to_end` | command raises `UserFacingError` through a real `CoreCommandTree.on_error` with `FakeInteraction`: ephemeral message sent, row rolled back. |

### 12.6 Alternatives rejected

| Alternative | Why not |
|---|---|
| Injected parameter `session: AsyncSession` hidden via a rewritten `__signature__` | The function's real signature then lies to readers, linters and type checkers (the parameter exists but callers never pass it); `ParamSpec`/`Concatenate` cannot express "remove this keyword parameter" on methods. A forgotten decorator turns it into a confusing `TypeError: unsupported type annotation`. Possible later as sugar on top of `get_session`. |
| `ContextVar[AsyncSession]` + `current_session()` | Hidden global dependency, the same family of problem as the singleton the brief bans; tests must set/reset it; works across tasks in surprising ways (tasks spawned by the command inherit the session and use it after commit). |
| Tree-level wrapper (override `CommandTree._call` or `Command._do_call`) | Private API; `_call` catches `AppCommandError` itself and calls `on_error` internally, so the wrapper would not see exceptions and would commit failures. Also opens a session for commands that need none. |
| Listening to `app_command_completion` to commit | Dispatched as a separate task after the command; commit happens after the reply and a failure is detached from the command; no event on failure. |
| Per-repository-call sessions (`with_session`) | The Glow/DSB flaw: no transaction across a command. |
| Lazy session opened on first `get_session` | A session object is cheap (no connection until the first statement), so laziness buys nothing and adds states to test. |
| `Database.transaction()` used by hand in every command | Boilerplate and easy to get wrong; the decorator is that code, written once. |

## 13. Clients

`infrastructure/clients/` is the place for outside HTTP APIs. For `v0.1.0` it contains one
small base, because every future client (a Top.gg-like API) would otherwise repeat the
same session/timeout/error code:

```python
class BaseHttpClient:
    def __init__(self, base_url: str, *, session: aiohttp.ClientSession | None = None,
                 timeout: float = 10.0, headers: Mapping[str, str] | None = None) -> None: ...
    async def request_json(self, method: str, path: str, **kwargs) -> Any: ...
    async def aclose(self) -> None: ...        # closes the session only if it created it
```

- A non-2xx or transport error raises `ExternalServiceError` (carries status and a
  *sanitised* message: no URL query string, no headers).
- The `aiohttp.ClientSession` is created lazily inside the running loop (not in `__init__`)
  and can be injected, so tests pass a fake or an `aiohttp` test server.
- Tokens for a client come from the app's settings (`SecretStr`), are given to the client
  constructor and put in headers; the base never logs headers.
- A client is an ordinary object created in the composition root (or the bot's
  `configure()`), registered with `bot.register_cleanup(client.aclose)`.
- No retries/backoff/caching in the base: there is no first user to tell what is needed.

## 14. UI kit

`ui/` builds embeds and views. It never touches the database (no import of
`infrastructure`), and business logic never imports it.

### 14.1 Embed helpers (`ui/theme.py`, `ui/embeds.py`)

```python
@dataclass(frozen=True, slots=True)
class EmbedTheme:
    info: discord.Colour; success: discord.Colour; warning: discord.Colour; error: discord.Colour
    footer: str | None = None

DEFAULT_THEME: Final[EmbedTheme]          # immutable constant

def info_embed(title: str, description: str | None = None, *, fields: Sequence[EmbedField] = (), theme: EmbedTheme = DEFAULT_THEME) -> discord.Embed
def success_embed(...); def warning_embed(...); def error_embed(...)     # same signature
def truncate(text: str, limit: int) -> str                                 # adds "…", never splits past the limit
EmbedField = NamedTuple("EmbedField", name=str, value=str, inline=bool)
```

Helpers truncate to Discord's limits (title 256, description 4096, field name 256, field
value 1024, 25 fields) so a long participant list cannot make the API call fail. Apps pass
their own `EmbedTheme` explicitly (the rubidium-bot has one); a frozen module constant is not
shared mutable state.

### 14.2 Status message (`ui/status.py`)

For the "one message, edited at each step" flow (Secret Santa: received → drawing →
sending n/N → finished with summary).

```python
class MessageEditor(Protocol):                       # the seam; the Discord adapter and the fake implement it
    async def send(self, embed: discord.Embed) -> None: ...     # first message (response or followup)
    async def edit(self, embed: discord.Embed) -> None: ...

class InteractionEditor:                             # adapter over a discord.Interaction
    def __init__(self, interaction: discord.Interaction, *, ephemeral: bool = True) -> None: ...

class StatusMessage:
    def __init__(self, editor: MessageEditor, *, title: str, theme: EmbedTheme = DEFAULT_THEME,
                 min_edit_interval: float = 1.0, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...

    @classmethod
    def for_interaction(cls, interaction, *, title: str, ephemeral: bool = True, **kw) -> "StatusMessage"

    async def start(self, text: str) -> None
        # "received": posts the message (response.send_message if the interaction is
        # unanswered, edit_original_response if it was deferred)
    async def step(self, text: str) -> None
        # replaces the current step text: "Drawing…"
    def progress(self, label: str, *, total: int) -> StatusProgress
        # async context manager / object: `await p.advance(n=1)`, shows "Sending… 3/10 ███░░░"
    async def finish(self, *, summary: Sequence[EmbedField] = (), text: str | None = None,
                     footer: str | None = None) -> None
        # final success embed with the summary fields; always flushed (not throttled)
    async def fail(self, text: str) -> None
        # final error embed (used when the command wants to show a controlled failure
        # on the same message; unexpected errors still go through the error handler)
```

Usage (the Secret Santa shape):

```python
status = StatusMessage.for_interaction(interaction, title="🎁 Secret Santa")
await status.start("Request received")
await status.step("Drawing names…")
...
async with status.progress("Sending messages", total=len(people)) as sending:
    for person in people:
        ok = await deliver(person)
        await sending.advance()
await session.commit()
await status.finish(summary=[EmbedField("Participants", str(n), True),
                             EmbedField("Delivered", str(ok_count), True),
                             EmbedField("Failed", str(failed_count), True),
                             EmbedField("What to do", "Ask them to open their DMs…", False)])
```

Design points:

- **Pure rendering.** `StatusRenderer` turns state (`title`, step history, progress, final
  summary) into a `discord.Embed`; it has no I/O and is unit-tested on its own. Steps already
  done are shown as ✅ lines, the current one as ⏳, so one message tells the whole story.
- **Throttled edits.** Discord rate-limits message edits; `advance()` updates the state at
  once but edits at most every `min_edit_interval` seconds (default 1 s), and `step`/
  `finish`/`fail` always flush. The first and last edits are never dropped. `clock` and
  `sleep` are injected, so tests run instantly and deterministically.
- **Serialised.** An `asyncio.Lock` keeps edits ordered; a late progress edit cannot
  overwrite the final one (after `finish`/`fail`, further calls raise `RuntimeError`).
- **Ephemeral by default, deferred correctly.** `InteractionEditor` uses
  `interaction.response.send_message(..., ephemeral=)` first, or
  `edit_original_response` when the command had deferred; the helper never calls
  `response` twice. Using it with `defer(ephemeral=True)` makes error followups private too.
- **Token lifetime.** `edit_original_response` works for 15 minutes after the interaction;
  past that, `edit` raises `ExternalServiceError`-free `discord.HTTPException`, caught once,
  logged at WARNING, and the status message stops editing (the command itself is not failed
  by a cosmetic update).
- **No sensitive data.** The helper renders only what it is given; the docs warn against
  putting private data into steps (Secret Santa: counts only, never who gives to whom).
- Rejected: editing a plain text message (embeds give structure); a `progress_bar` utility
  separate from the status message (DSB: one-purpose, two places to keep consistent); a
  context-manager-only API (`async with StatusMessage(...)` swallows the final summary
  semantics; the explicit `finish` is clearer).

### 14.3 Views (`ui/views.py`)

```python
class BaseView(discord.ui.View):
    def __init__(self, *, timeout: float = 180.0, clear_on_timeout: bool = True) -> None: ...
    async def send(self, interaction: discord.Interaction, **kwargs) -> None
        # response.send_message(view=self, **kwargs) or followup; remembers how to edit it back
    async def on_timeout(self) -> None          # clears components (edits the message with view=None)
    async def on_error(self, interaction, error, item, /) -> None   # -> bot.error_handler

class SingleUserView(BaseView):
    def __init__(self, user_id: int, *, timeout: float = 180.0, **kw) -> None: ...
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool
        # False and an ephemeral "This menu belongs to someone else." for other users
```

- `on_timeout` edits through the stored interaction (`edit_original_response(view=None)`);
  edits fail silently with a DEBUG log when the message is gone or the token expired.
  `timeout` is capped at 14 minutes (`ValueError` above) because the edit token lives 15.
- `SingleUserView.interaction_check` compares `interaction.user.id` (works in DMs and
  guilds: users, not members).
- `BaseModal` mirrors `on_error` only. No persistent views in v0.1.0 (they need stable
  `custom_id`s and a `setup_hook` registration; add when an app needs them).
- Views hold no database session and no repository (a session must not outlive the
  command); a view callback that needs the database opens its own unit of work through
  `bot.database.transaction()` — documented, with the note that it is a separate
  transaction from the command's.

## 15. Testing support

Everything the library does with Discord goes through a narrow seam, so an app's tests do
not need Discord (details and examples in [testing](testing.md)):

- `discord_bot_core.testing.FakeInteraction` — the attributes the core reads
  (`extras`, `client`, `user`, `guild_id`, `guild`, `channel_id`, `command`, `type`,
  `response`, `followup`), with `FakeResponse`/`FakeFollowup` that record what was sent
  (content, embed, ephemeral flag, order). Guild may be `None` (DM).
- `memory_database()` — async context manager yielding a `Database` on in-memory SQLite.
- `StatusMessage` takes a `MessageEditor`, so tests use a recording editor, no fake of
  discord.py internals.
- Settings are built by constructor in tests.
- `CoreBot(settings, database=..., error_handler=...)` is constructible without a
  connection (`discord.Client.__init__` does no I/O).
- The `testing` package is in the wheel (it is small, imports no pytest, and an app's
  tests need it; a second distribution would be overkill).

The library's own suite: unit tests per module (`tests/` mirrors `src/`), `tests/integration/`
for the database and the real `app_commands.Command` construction, `pytest-asyncio` in
`auto` mode, coverage reported by `pytest-cov` (`--cov=discord_bot_core
--cov-report=term-missing --cov-report=xml`, in `addopts`, so `uv run pytest` is the CI
command). No `fail_under`: tests exist to find problems, not to hit a number (review
decision 7, §19).

## 16. Documentation plan

The brief wants these pages; the design PR contains the first block, the implementation
PRs add the second block together with the code they describe (docs are part of each PR).

| Page | Where | Written in |
|---|---|---|
| `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `.env.example` | root | design PR |
| `docs/design.md` (architecture and layers) | docs | design PR |
| `docs/getting-started.md`, `docs/configuration.md`, `docs/testing.md` | docs | design PR |
| `docs/dev-guild-and-sync.md` | docs | PR "admin commands" (derived from 8) |
| `docs/extensions.md` | docs | PR "extensions" (derived from 9) |
| `docs/database.md` — database, Alembic, per-command session | docs | PR "database + session" (12, 11) |
| `docs/error-handling.md` | docs | PR "errors" (10) |
| `docs/ui-kit.md` | docs | PR "ui" (14) |
| `docs/releasing.md` (or the CONTRIBUTING section, linked) | docs | PR "release" |

Docstrings: Google style, on every public class/function, with an example where use is
not obvious; enforced by ruff's `D` rules with `convention = "google"` (public API only).

## 17. Implementation steps

Each step is one small PR (conventional commit title), reviewed by a worker who did not
write it, with its tests and its docs page.

| # | PR | Content | Tests |
|---|---|---|---|
| 1 | `chore: project skeleton` | `pyproject.toml` (hatchling, uv, ruff, pytest, coverage config), `uv.lock`, CI workflow (python 3.14, `uv run pytest`, ruff check + format --check), `py.typed`, package `__init__` | import test: no side effects; ruff and pytest run green in CI |
| 2 | `feat(settings): CoreSettings` | settings package, `describe()`, `load()` with secrets dir; `docs/configuration.md` is already there (update if drifted) | required fields fail; secrets masked in repr/dump; env > secrets file; file with trailing newline; missing secrets dir no warning; unknown env ignored |
| 3 | `feat(logging): configure_logging` | logging_config | idempotent; level applied; no f-string rule in ruff |
| 4 | `feat(errors): exceptions and ErrorHandler` | errors package, `testing.FakeInteraction` (first version) | table in 10: each exception class → message/ephemeral/log level; unexpected → id in reply and in log record, traceback in `exc_info`, DM (`guild_id=None`); response already done → followup; HTTP failure on reply swallowed; channel report rate limit; channel missing; no exception message in the report |
| 5 | `feat(bot): CoreBot and CoreCommandTree` | bot package without admin/ext/db yet; `launch()` | bot builds without network; tree `on_error` delegates; startup log has no secret; no `on_ready` registered |
| 6 | `feat(db): Database, Base, BaseRepository` | database package, `memory_database()` | engine from URL; SQLite pragma; `transaction()` commit/rollback/close and cancellation; naming convention applied |
| 7 | `feat(commands): transactional` | decorator, `get_session`, checks | the whole table of 12.5 |
| 8 | `feat(extensions): ExtensionManager` | discovery, manager, `bot` integration | discovery on a fixture package (skips `_x`, sorted); load/unload/reload map errors; cannot load outside package; `load_all` continues after failure |
| 9 | `feat(core-cmds): sync and extension commands` | core cog (`/core`), autocomplete, `sync_dev_guild_once` | owner-only (non-owner gets `OwnerOnlyError`); registered in the dev guild only (`tree.get_commands(guild=dev)`); dev reset/copy removes stale; prod does not copy; autocomplete filters, ≤ 25, empty for non-owner; sync never called at start (spy on `tree.sync`) |
| 10 | `feat(migrations): alembic helper` | `migrations.py`, doc | `run_migrations` offline/online against a temp SQLite with a sample model; missing URL error |
| 11 | `feat(ui): embeds, status message, views` | ui package | renderer snapshots; throttle with fake clock; ordering; ephemeral/deferred path; view owner check; timeout clears; `timeout` cap |
| 12 | `feat(clients): BaseHttpClient` | clients base | injected session; error mapping; no secret in messages |
| 13 | `docs: ...` pages listed in 16, `chore: release v0.1.0` | changelog entry, annotated tag by Tim | link check in CI (optional) |

PRs 2–4 are independent of each other and can be written in parallel; 5 needs 2–4; 7 needs 6;
9 needs 5, 8. The rubidium-bot can start on PR 5's interfaces once 5–7 are merged and tagged
as a pre-release (`v0.1.0-rc1`... or main via a commit-pinned git dependency).

## 18. Risks and how the design handles them

| Risk | Handling |
|---|---|
| discord.py private API drift (`_call`, `_do_call`) | The core uses none: only `on_error`, `interaction_check`, `setup_hook`, `add_cog`, `copy_global_to`, `sync`, public `Command.parameters`. Upper bound `<3`. A CI job on `lowest-direct` plus the lock catches drift. |
| `transactional` assumes the interaction is the last positional argument | True for every discord.py 2.x call path **[verified: `_do_call`]**, asserted by a test that goes through `Command._invoke_with_namespace`-free construction (`Command.callback` call shape) and by `FakeInteraction` calls. If it ever changes, the test fails first. |
| Signature evaluation at decoration time | `eval_str=True` fallback to raw signature on `NameError`; test with `TYPE_CHECKING` import. |
| Long-held SQLite write lock | Documented (12.3); transaction per command is short for typical commands. |
| Deferred non-ephemeral command + error reply visibility | Documented; status message defers ephemeral. |
| Error report flood | Rate limit per (command, exception class). |
| Admin commands visible to non-owners in dev guild | They are rejected by the owner check; they can still *see* the commands in the picker. Discord permissions (`default_permissions(administrator=True)`) are added as a second layer; the check is what is trusted. Autocomplete returns `[]`. |
| Owner-only relies on `Bot.is_owner` (an API call to `application_info` once, cached) | It is a coroutine cached by discord.py; failure → `CheckFailure` path, deny by default. |
| Personal data in logs | Options are never logged; the error report omits messages; documented for app authors. |
| Import-time side effects (engine, settings) | None by design; tested. |
| `interaction.extras` is public but semi-obscure | The key is a private sentinel; the accessor is the only supported way; documented. |

## 19. Review decisions (Tim, 2026-11-15 — all open questions resolved)

1. **Bootstrap sync:** approved — gateway-less one-shot `sync_dev_guild_once` (§8).
2. **Admin group name:** `/core` (fixed), so `/admin` stays available for apps.
3. **`owner_ids` setting:** dropped — the application's owner/team is the only owner
   (§5); discord.py's `is_owner` provides exactly that by default.
4. **Type checker in CI:** approved — mypy (or pyright) job added alongside ruff and
   pytest (§2, CONTRIBUTING).
5. **`environment`:** default `prod`, not required.
6. **Intents:** the core's default is `Intents.default()` (no privileged intents);
   per-app intent needs (e.g. `members`) are the app's choice, not the core's.
7. **Coverage threshold:** none. Coverage is *reported* (term + xml) but there is no
   `fail_under` — tests exist to find problems, not to hit a number; business logic
   must be tested, the rest follows.
8. **Error-channel content:** location only (no exception message) stays the default,
   and the channel id is a setting (`error_log_channel_id`) — privacy first.
9. **Dev `sync global`:** allowed, with a warning in the reply (§8).
10. **Secrets dir:** `/run/secrets` default via `load(secrets_dir=...)`; no
    `SECRETS_DIR` env var.

## 20. Traceability: brief requirement → design

Brief section "discord-bot-core":

| Requirement | Satisfied by |
|---|---|
| A bot subclassing `CoreBot` with no cogs runs and offers the below | 7 (`setup_hook` loads admin cog, no cog required), step 5 test "bot builds without cogs" |
| **Dev guild**: configured; core commands only there | 5 (`dev_guild_id` required), 8 (`add_cog(guild=Object(dev))`, `guild_only`) |
| In dev, app commands copied to dev guild and synced there; in prod global | 8 (reset + copy + sync in dev; `sync global` in prod; `environment`) |
| No automatic global sync at every start; sync is a command | 8 ("Sync is only a command"; no `on_ready`; test spies `tree.sync`), 7 |
| **Sync commands** (dev guild, owner only): global, dev guild, one guild by id | 8 table: `/core sync global|dev|guild` + `owner_only` (12.x checks, 3 `commands/checks.py`) |
| **Extension commands** (dev guild, owner only): load, unload, reload, list, autocomplete | 9 table (`/core ext ...`), autocomplete notes, `owner_only` |
| Extensions discovered from a package the app names | 9 `discover_extensions(package)`, `CoreBot(extensions_package=...)` |
| **Settings**: pydantic-settings, validated at start | 5 (`CoreSettings.load()`, stops at start) |
| No defaults for ids or secrets, no hard-coded ids | 5 (`discord_token`, `dev_guild_id` required; library has no id literals) |
| Secrets as `SecretStr`, from env or files (`secrets_dir`), never logged | 5 (`SecretStr`, `_secrets_dir`, `describe()`, masked repr), [configuration](configuration.md) |
| **Error handling**: one `on_error` on the command tree | 10 (`CoreCommandTree.on_error`, verified signature) |
| Domain exception with user message → that message, ephemeral | 10 (`UserFacingError`, table row 1, step 4) |
| Anything else → generic message with short error id, logged with traceback, command, user and guild ids | 10 (unexpected path, `token_hex(4)`, `exc_info`) |
| Optional error-log channel | 5 (`error_log_channel_id`), 10 point 5 |
| Works in DMs (no `interaction.guild` assumptions) | 10 point 3 (`guild_id`), 6 (interaction logging), step 4 DM test, 14.3 (`user.id`) |
| **Logging**: standard `logging`, configured once, level from settings | 6 |
| **Database infrastructure**: SQLAlchemy 2 async, engine + session factory from URL in settings | 11 (`Database`) |
| A declarative base | 11 (`Base`, naming convention) |
| Alembic support for apps | 11.1 (`run_migrations`, app `env.py`) |
| Optional: a bot without a database URL runs | 5 (`database_url` optional), 11 ("Optional"), 7 |
| **Transactional session per command**: lives for the whole command, commit on success, rollback on raise, close | 12.2 + 11 (`transaction()`) |
| Repositories and services receive the session; they don't open their own | 12.4, 11 (`BaseRepository`) |
| Injected parameter must not show up as an option | 12.1, 12.2 (signature unchanged, accessor), test `test_session_not_an_option` |
| Design it and test it: commit path, rollback path, two repositories in one transaction | 12.5 (`test_commit_on_success`, `test_rollback_on_exception`, `test_two_repositories_one_transaction`, ...) |
| **Clients** (`infrastructure/clients`): place for outside HTTP APIs, empty except a base if useful | 13 (`BaseHttpClient`) |
| **UI kit**: base views (single-user, auto-clear on timeout) | 14.3 (`BaseView`, `SingleUserView`) |
| Embed helpers | 14.1 |
| Status message helper | 14.2 |
| Business logic never builds embeds; UI never touches the database | 1 (layers), 14 (no import of `infrastructure`), 4 (services without `ui`) |
| **No singletons**; bot and services passed explicitly; testable without Discord | 1, 4 (composition root, constructor injection), 15 |
| Public repo, MIT | `LICENSE`, README |
| Released by annotated tags (`v0.1.0`), changelog entry per release | CONTRIBUTING (release steps), `CHANGELOG.md`, 2 (SemVer) |
| `rubidium-bot` depends on a tag (git dependency) | 2 (extras), [getting-started](getting-started.md) (dependency line), CONTRIBUTING |

Brief section "Both repos" (as it applies to the core):

| Requirement | Satisfied by |
|---|---|
| Latest stable Python and discord.py | 2 (`>=3.14`, `discord.py>=2.7.1`) |
| uv, `pyproject.toml`, `uv.lock` committed; `src/` layout | 2, 3, CONTRIBUTING |
| ruff (lint+format) and pytest in CI, coverage reported; type hints everywhere | 2, 15, CONTRIBUTING |
| Tests need no Discord: fakes or thin adapters | 15, [testing](testing.md) |
| `.env.example`, names only; docs and code in English | `.env.example`, all docs |

Brief section "Documentation" (as it applies to the core):

| Requirement | Satisfied by |
|---|---|
| README: what, quick start, run locally, tests, links | `README.md` |
| docs: architecture/layers, getting started, configuration, dev guild and sync, extensions, database and session, error handling, UI kit, testing, releasing | 16 (page map), `design.md`, `getting-started.md`, `configuration.md`, `testing.md`; the rest in the implementation PRs |
| Docstrings on every public class/function, Google style, examples | 16, CONTRIBUTING (ruff `D`, google convention) |
| LICENSE, CHANGELOG (Keep a Changelog), CONTRIBUTING (setup, checks, commit style, release steps) | root files |
| Conventional commits; small PRs reviewed by another worker | CONTRIBUTING, 17 |

Brief "flaws to not repeat" (library side): `SingletonMeta` → 4; hidden `Bot()` access → 4;
`load_dotenv`/`os.getenv`, hard-coded ids, committed token → 5; per-call session with
commit in `finally` → 11/12; `deleted_at is None` → 11 (no soft delete; rule);
`.join` on a list → 9 (discovery via `pkgutil`); no owner check → 8/9 (`owner_only` on
every core command, tested); `on_ready` sync and TTS greeting → 7, 8; bare `except`,
`raise e`, f-string logs, `guild.name` on DMs → 6, 10, ruff rules in CONTRIBUTING; embeds in
services → 1, 14; unpinned deps, no lock, no tests → 2, 15.

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, a minor release may contain breaking changes; they are
listed under **Changed** or **Removed**.

## [Unreleased]

### Added

- Core commands: the owner-only, guild-only `/core` group (`/core sync global|dev|guild`,
  `/core ext load|unload|reload|list` with autocomplete), added to the dev guild only;
  `CoreBot.setup_hook` adds it and loads the extensions; `sync_dev_guild` resets the dev
  guild while keeping `/core`; `ExtensionManager` wired into `CoreBot`.
- Guides: [dev guild and sync](docs/dev-guild-and-sync.md),
  [extensions](docs/extensions.md).
- UI kit (`discord_bot_core.ui`): `EmbedTheme`/`DEFAULT_THEME`, `EmbedField`,
  `info_embed`/`success_embed`/`warning_embed`/`error_embed` and `truncate` (Discord
  limits enforced); `StatusMessage`/`StatusProgress`/`StatusRenderer` with throttled,
  serialised edits and `InteractionEditor` (ephemeral, deferred-aware); `BaseView`,
  `SingleUserView` and `BaseModal` delegating errors to the error handler; guide
  [`docs/ui-kit.md`](docs/ui-kit.md).
- Commands package: `@transactional` decorator + `get_session(interaction)` per-command
  session, `owner_only` check.
- `logging_config.configure_logging` (single tagged stderr handler, idempotent).
- Errors package (`CoreError` hierarchy, `ErrorHandler`) and `testing.FakeInteraction`.
- Database package: `Database` (transaction commit/rollback/close, SQLite pragmas,
  `StaticPool` for `:memory:`), `Base` with naming convention, `BaseRepository`,
  `testing.memory_database()`.
- Alembic helper `run_migrations` (offline/online, SQLite batch mode, URL from settings,
  never in `alembic.ini`) and the [database guide](docs/database.md).
- Project skeleton: `pyproject.toml` (hatchling, uv, ruff, pytest, coverage, mypy),
  `uv.lock`, CI workflow, `src/` layout with the import-side-effect-free package and
  `py.typed`.
- Design document ([`docs/design.md`](docs/design.md)): package layout, dependency
  injection, settings, logging, the bot, dev guild and sync, extensions, error handling,
  database infrastructure, the transactional session per command, clients, UI kit,
  testing support, implementation steps and risks. No code yet.
- Guides: [getting started](docs/getting-started.md),
  [configuration](docs/configuration.md), [testing](docs/testing.md).
- Repository files: `README.md`, `CONTRIBUTING.md`, `LICENSE` (MIT), `.env.example`.
- Settings package: `CoreSettings`, `load(secrets_dir=...)`, `describe()`.
- Bot package: `CoreBot`, `CoreCommandTree` (on_error delegation, invocation logging),
  `launch()`, sync helpers, `register_cleanup`.

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, a minor release may contain breaking changes; they are
listed under **Changed** or **Removed**.

## [Unreleased]

### Added

- Commands package: `@transactional` decorator + `get_session(interaction)` per-command
  session, `owner_only` check.
- `logging_config.configure_logging` (single tagged stderr handler, idempotent).
- Errors package (`CoreError` hierarchy, `ErrorHandler`) and `testing.FakeInteraction`.
- Database package: `Database` (transaction commit/rollback/close, SQLite pragmas,
  `StaticPool` for `:memory:`), `Base` with naming convention, `BaseRepository`,
  `testing.memory_database()`.
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

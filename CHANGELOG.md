# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, a minor release may contain breaking changes; they are
listed under **Changed** or **Removed**.

## [Unreleased]

### Changed

- `CoreBot.sync_dev_guild_once()` (the `sync-dev` bootstrap) now publishes **only the
  `/core` group** to the dev guild: it removes every other guild-scoped command and no
  longer copies the global commands over. A fresh application gets exactly the commands
  needed to load extensions itself; cog commands appear after `/core ext load` +
  `/core sync dev`.
- CI only: `.github/workflows/main.yml` no longer has `deploy-dev`/`deploy-prod` jobs
  and no longer triggers on `v*` tags — a library has no compose file, so there is
  nothing to deploy. `docs/releasing.md` updated accordingly.

### Added

- i18n module (`discord_bot_core.i18n`): `TranslationCatalog` (symbolic keys →
  per-locale strings), `CoreTranslator` (a `discord.app_commands.Translator` that
  localizes command descriptions at sync time and runtime replies per invoking
  user's locale, falling back to `default_locale`) and `CORE_CATALOG`.
  `CoreBot` builds the translator (or accepts one) and registers it in
  `setup_hook`; new `default_locale` setting (default `en-US`). The `/core sync`
  success reply is localized as the first example; command names are not
  translated.
- All remaining user-facing strings in the core are now in `CORE_CATALOG` (both
  `en-US` and `fr`): the `/core` group/subcommand descriptions and parameter
  descriptions (via `locale_str`, translated at sync time) and the `/core` replies
  and embeds (sync fields, ext list/actions, errors) translated at runtime through
  the new `i18n.translate(interaction, key, **format_args)` helper, which falls back
  to the English catalog text when no translator is available. The error handler
  translates its ephemeral reply per the invoking user's locale (the error-log
  channel embed intentionally stays in English); application-supplied
  `UserFacingError` messages are passed through unchanged. The UI kit's
  `OTHER_USER_MESSAGE` is now the `ui.view.other_user` key.
- Guides: [error handling](docs/error-handling.md) and
  [releasing](docs/releasing.md); README links every docs page.
- Real-database transactional tests (`tests/commands/test_transactional_real_db.py`):
  the §12.5 contract against `testing.memory_database()` with commit/rollback/close
  asserted on rows a second session sees.

### Fixed

- i18n runtime helpers now resolve against the bot's catalogs, not only
  `CORE_CATALOG`: new `i18n.runtime.use_catalogs(catalogs)` (re-exported as
  `i18n.use_catalogs`) is called by `CoreBot.setup_hook` with the translator's
  catalogs, so `default_text`/`translate` find application keys (e.g.
  `secret_santa.*`) in their `en-US`/locale fallback without apps mirroring their
  keys into `CORE_CATALOG`. `CORE_CATALOG` remains the core's own catalog; before
  wiring, the helpers search it alone.
- `UserFacingError` now accepts an optional `message_key` and `format_args`; the
  error handler replies with that catalog key translated to the invoking user's
  locale while the exception's `message` stays the English logged/fallback text.
  The core's own failures (`core.ext.error.no_manager`, `core.sync.guild.invalid`)
  use it, so their French translations reach the user; plain
  `UserFacingError(message)` behaviour is unchanged.
- `i18n.translate` treats a translator result that is `None` or still echoes its
  input (the key or the `locale_str`) as untranslated and falls back to the
  `en-US` text, and a `{placeholder}`/argument mismatch now returns the unformatted
  text instead of raising — a bad catalog entry can no longer break a reply.

### Changed

- The placeholder Protocols in `bot`, `errors` and `extensions` are replaced by the
  real `Database`/`CoreSettings` types; `CoreBot.database` is `Database | None`.
- `@transactional` reuses the command's session on a nested decorated call instead of
  opening a second transaction (design §12: one session per command invocation).

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
- Clients package: `BaseHttpClient` (lazy or injected `aiohttp.ClientSession`,
  `request_json` raising a sanitised `ExternalServiceError`, `aclose`).
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

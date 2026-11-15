# Configuration

`CoreSettings` (`discord_bot_core.settings`) is a pydantic-settings model. It is
validated when you call `CoreSettings.load()` (or `AppSettings.load()` for your subclass):
a missing or invalid setting stops the process at start, with one line per bad field
(field name only, never the value) and exit status 2. See [design section 5](design.md#5-settings)
for the reasons behind each choice.

This page lists **names only**. Never put a real value in this repository.

## Settings

Environment variable names are the field names, case-insensitively. The secrets file name
is the field name, lower case, in the secrets directory (see below).

| Field | Type | Required | Secret | Env var | Secrets file | Default |
|---|---|---|---|---|---|---|
| `discord_token` | `SecretStr` | **yes** | **yes** | `DISCORD_TOKEN` | `discord_token` | none |
| `dev_guild_id` | `PositiveInt` | **yes** | no | `DEV_GUILD_ID` | — | none |
| `environment` | `Environment` (`dev` or `prod`) | no | no | `ENVIRONMENT` | — | `prod` |
| `log_level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` | no | no | `LOG_LEVEL` | — | `INFO` |
| `error_log_channel_id` | `PositiveInt \| None` | no | no | `ERROR_LOG_CHANNEL_ID` | — | `None` (feature off) |
| `database_url` | `SecretStr \| None` | no | **yes** (the URL may embed a password) | `DATABASE_URL` | `database_url` | `None` (the bot runs without a database) |

Notes:

- Only the secret fields are meant to come from files; a platform that mounts one file per
  secret (Docker secrets) creates `discord_token` and `database_url` (if you use a
  database). pydantic-settings would also read a file for another field name, but the
  non-secret settings belong in the environment or the compose file.
- `environment`: `dev` copies the app's commands to the dev guild on `/core sync dev`;
  `prod` publishes global commands only with `/core sync global`. Nothing is ever synced
  at start in either case.
- `log_level`: `DEBUG` makes discord.py's gateway logger verbose and it can print
  payloads. Do not use `DEBUG` in production.
- `error_log_channel_id`: when set, unexpected errors post a short report (error id,
  command, ids, exception class, code location; never the message or the traceback) to
  that channel.
- `database_url`: a SQLAlchemy async URL (`sqlite+aiosqlite:///...` needs the `sqlite`
  extra, `postgresql+asyncpg://...` the `postgres` extra). Nothing creates tables or runs
  migrations at start.
- An app adds its own settings by subclassing `CoreSettings`. A field without a default is
  required, and it fails at start like the two required core fields.

## Loading priority

Highest first:

1. Arguments passed to the constructor (`AppSettings(discord_token=...)`), used by tests.
2. Environment variables.
3. The `.env` file in the working directory.
4. The secrets directory.

So an environment variable overrides a secrets file, and a secrets file is the fallback.
Unknown variables are ignored (`extra="ignore"`), and settings are immutable after loading
(`frozen=True`).

## `.env`

`CoreSettings` reads `.env` itself (pydantic-settings `env_file`); it does not copy it into
`os.environ`, and the library never calls `load_dotenv` or `os.getenv`. Copy
[`.env.example`](../.env.example) to `.env` for local runs. `.env` must stay out of git.

## Secrets directory

`CoreSettings.load(secrets_dir=DEFAULT_SECRETS_DIR)` reads secrets from files, one file per
secret, named after the field. `DEFAULT_SECRETS_DIR` is `/run/secrets`, where Docker and
Compose mount secrets. The trailing newline of a file is stripped.

- If the directory does not exist (a laptop), it is simply not used, with no warning.
  `model_config` does not hard-code `secrets_dir`, because pydantic-settings warns about a
  missing one.
- On the Rubidium Labs platform, label the service `homelab.secrets: "true"` and the
  platform mounts `/run/secrets/<setting>`; no extra configuration is needed.
- To use another directory, call `AppSettings.load(secrets_dir=Path("/path"))`. There is no
  environment variable for it.

## What is never logged

- `SecretStr` masks `repr`, `str` and `model_dump`; the core calls `.get_secret_value()`
  only where it must (logging in to Discord, building the database engine, the Alembic
  helper).
- The startup log line comes from `CoreSettings.describe()`: non-secret fields plus
  `database: configured` or `not configured`. The database URL is not printed, not even
  redacted. Validation errors name the field, never its value.
- SQLAlchemy's `echo` is not exposed (it logs bound parameters).
- Command options are never logged; the error-log channel report omits exception
  messages. Do not put sensitive data in a `UserFacingError` message either, because
  it is logged at INFO.

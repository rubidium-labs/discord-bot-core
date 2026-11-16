# Error handling

One `on_error` on the command tree (`CoreCommandTree.on_error`) routes every command
failure. App code raises domain exceptions; the core turns them into replies and logs.
`ErrorHandler.classify(error)` is the single mapping; `ErrorHandler.handle(...)` runs it.

## The classification table

`ErrorHandler.classify` maps the unwrapped exception to the reply message and log level.
Raise the most specific exception available.

| Exception | User sees | Log level |
|---|---|---|
| `UserFacingError` | its message, verbatim | INFO |
| `OwnerOnlyError` (a `CheckFailure`) | the check-failure message | INFO |
| `app_commands.NoPrivateMessage` | the no-DM message | INFO |
| `MissingPermissions` / `BotMissingPermissions` | the missing permissions, named | INFO |
| `CommandOnCooldown` | "Try again in N s." | INFO |
| `CommandNotFound` / `CommandSignatureMismatch` | the out-of-date message | WARNING |
| `TransformerError` | "Invalid value for `<option>`." | INFO |
| any other `CheckFailure` | the check-failure message | INFO |
| anything else | "Something went wrong. Error id `abcd1234`." | ERROR, with traceback |

All replies are ephemeral. Unexpected errors get a short random id
(`secrets.token_hex(4)`) that appears both in the reply and in the log record
(`extra={"error_id": ...}`), so a user can quote the id and you can find the traceback.
The exception message itself is never sent to the user and never put in the error-log
channel report.

`DatabaseNotConfiguredError`, `NoActiveSessionError` and `ExternalServiceError` are
`CoreError` subclasses meant for app code to raise; if they escape to the tree they fall
into the generic unexpected path (ERROR + traceback), which is the safe default.

## Reply mechanics

- The reply is sent with `response.send_message(..., ephemeral=True)`.
- If the interaction was already responded to or deferred, the reply goes to
  `followup.send(..., ephemeral=True)` instead — the command never fails twice.
- If the reply itself fails, it is logged with `logger.exception` and swallowed: the
  error handler never raises.
- DMs work: nothing assumes `interaction.guild` is set. The log record and the optional
  channel report use `interaction.guild_id` and `interaction.channel_id` (both `None`
  in DMs).

## Error-log channel

If `error_log_channel_id` is set in the settings, a short report is posted there:
**location only** — command name, user id, guild id, channel id, error id. No exception
message, no options. Reports are rate limited per (command, exception class) with a
suppression counter, so a flood cannot spam the channel. A missing or unreachable
channel is logged and skipped.

## What is never logged

- Command options (they may contain personal data).
- Secrets — settings are `SecretStr`, their repr is masked.
- HTTP client headers and URL query strings.

## In tests

`testing.FakeInteraction` records replies, so a test asserts on
`interaction.response.messages` / `interaction.followup.messages` after invoking a
command through `ErrorHandler.handle(...)` — see [testing.md](testing.md).

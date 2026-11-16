# Dev guild and sync

Application commands are not published automatically: syncing is a command (or an explicit
one-shot), never a side effect of starting the bot. Discord rate-limits command syncs, and
a broken deploy should not wipe or spam the command list. The reasons are in
[design section 8](design.md#8-dev-guild-and-sync).

## Where the commands live

- Your cogs' commands (global `app_commands`) are registered in the tree as **global**.
- The core's `/core` group is added to the tree **scoped to the dev guild**, in dev and in
  prod alike. It exists only there, is `guild_only` (not usable in DMs) and carries the
  owner check: only the application's owner (or a team member) can run it.
- In **prod** nothing is copied to the dev guild automatically; global commands are
  published by `/core sync global`.
- In **dev** your commands are *copied* into the dev guild and synced there, so changes
  show up instantly and nothing leaks to other guilds.

## The sync commands

All are owner-only and exist only in the dev guild. Each replies with an ephemeral embed
showing the scope, the number of commands and their names.

| Command | Behaviour |
|---|---|
| `/core sync global` | `tree.sync()`: publishes the global commands. The `/core` group is guild-scoped, so it is not part of it. In dev the reply warns that global commands are normally not published there. Never blocked. |
| `/core sync dev` | prod: `tree.sync(guild=dev)` (admin commands only). dev: *reset, copy, sync* (below). |
| `/core sync guild <guild_id>` | `tree.sync(guild=Object(id))`: the guild-scoped commands of that guild (none by default; for apps that register per-guild commands). Replies with the count. `guild_id` is a text option parsed to `int` (Discord integers overflow options); bad input is a user-facing error. |

### Dev "reset, copy, sync"

`copy_global_to` *overrides* same-name commands but never removes commands that left the
global tree (for example after unloading a cog), so the dev guild would keep stale
commands. `CoreBot.sync_dev_guild` therefore:

1. removes every command from the dev guild's tree **except the `/core` group**,
2. calls `tree.copy_global_to(guild=dev)`,
3. calls `tree.sync(guild=dev)`.

It is idempotent, so it is safe to run on every `/core sync dev`, and it is also correct
after `/core ext reload`. Hitting the 100-command limit surfaces as the generic error path.

## First start (bootstrap)

On a fresh application the `/core` commands are not registered in Discord yet, and they are
what registers everything else. `CoreBot.sync_dev_guild_once()` is the explicit one-shot
for that: it logs in without the gateway (which runs `setup_hook`) and syncs the dev guild
only. Your app exposes it as a CLI command, `python -m my_bot sync-dev`:

```python
async def sync_dev() -> None:
    """One-shot: publish the commands to the dev guild, without a gateway connection."""
    settings = AppSettings.load()
    bot = MyBot(settings)
    async with bot:
        await bot.login(settings.discord_token.get_secret_value())  # runs setup_hook, no websocket
        commands = await bot.sync_dev_guild_once()
    print(f"Synced {len(commands)} commands to the dev guild.")
```

Run it by hand, on purpose. It is never part of a normal start.

## Sync is only a command

`setup_hook` never syncs, and the core registers no `on_ready` handler. After changing the
commands of an extension, run `/core sync dev` yourself.

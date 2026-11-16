# Extensions

An *extension* is a module or package inside your bot's cogs package that defines an
`async def setup(bot)` function. The core loads them at start (unless you turn it off) and
lets the owner load, unload and reload them at runtime without a restart. The reasons are
in [design section 9](design.md#9-extensions).

## Naming the package

Name the package once, when you build the bot:

```python
class MyBot(CoreBot):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__(settings, extensions_package="my_bot.cogs")
```

`CoreBot` builds an `ExtensionManager` for that package and, in `setup_hook`, loads every
discovered extension. A failing extension is logged with its traceback and the bot keeps
running, so an admin can fix it and `/core ext reload`.

## Discovery

`discover_extensions(package)` imports the package (not its modules) and lists the modules
and sub-packages it contains, sorted and fully qualified (for example
`my_bot.cogs.secret_santa`). Names starting with `_` are skipped. Whether a module really
defines `setup` is checked lazily when it is loaded, so discovery never runs extension code.

## The commands

All are owner-only and exist only in the dev guild.

| Command | Option | Autocomplete offers |
|---|---|---|
| `/core ext load` | `name` | unloaded extensions |
| `/core ext unload` | `name` | loaded extensions |
| `/core ext reload` | `name` | loaded extensions |
| `/core ext list` | — | — (embed: loaded / available) |

The `name` option takes a short name (`secret_santa`) or the full name
(`my_bot.cogs.secret_santa`). Autocomplete offers at most 25 choices filtered by the typed
substring, with the short module name as the label and the full name as the value. It
re-checks ownership itself (autocomplete does not run command checks) and returns nothing
for non-owners, so they never see extension names.

The manager only manages names **inside** the configured package: an owner cannot load an
arbitrary importable module (`os`, `anything.else`) through the command. discord.py's
`ExtensionAlreadyLoaded` / `ExtensionNotLoaded` / `ExtensionNotFound` /
`NoEntryPointError` / `ExtensionFailed` are mapped to a user-facing message naming the
module (never a traceback).

## After load, unload or reload

Loading, unloading or reloading an extension can change the command tree. The core does
**not** sync on its own: the reply tells you to run `/core sync dev`. In dev that reset,
copies and syncs, so the new commands show up at once; see
[dev guild and sync](dev-guild-and-sync.md).

## Testing an extension

Extensions are plain modules with a `setup`; test the cog's commands directly with the
fakes from `discord_bot_core.testing` (see [testing](testing.md)). The manager itself is
tested against a small stub bot that mimics the discord.py extension API, so no gateway is
needed.

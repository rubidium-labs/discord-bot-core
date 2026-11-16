# The UI kit

`discord_bot_core.ui` builds embeds, the one-message status flow and the base views and
modals. It never imports `infrastructure`, and business logic never imports it: a service
returns data, the command (or cog) turns it into embeds and views. The design is in
[design section 14](design.md#14-ui-kit).

## Embeds and the theme

`EmbedTheme` holds the four colours and an optional footer. Applications build their own
theme and pass it explicitly; `DEFAULT_THEME` is a frozen constant, not shared mutable
state.

```python
import discord
from discord_bot_core.ui import DEFAULT_THEME, EmbedField, EmbedTheme, success_embed

MY_THEME = EmbedTheme(
    info=discord.Colour.blurple(),
    success=discord.Colour.green(),
    warning=discord.Colour.orange(),
    error=discord.Colour.red(),
    footer="My Bot",
)

embed = success_embed(
    "Done",
    "All messages were delivered.",
    fields=[
        EmbedField("Delivered", "10", True),
        EmbedField("Failed", "0", True),
    ],
    theme=MY_THEME,
)
```

`info_embed`, `success_embed`, `warning_embed` and `error_embed` share one signature:
`(title, description=None, *, fields=(), theme=DEFAULT_THEME)`. They apply the theme's
colour and footer and enforce Discord's limits so a long participant list cannot make the
API call fail:

| Part | Limit |
|---|---|
| title | 256 |
| description | 4096 |
| field name | 256 |
| field value | 1024 |
| fields | 25 (the rest are dropped) |

`truncate(text, limit)` is the helper they use: it adds a `…` and never returns more than
`limit` characters. Use it yourself for content you build outside the helpers.

## The status message

`StatusMessage` posts one message and edits it at each step of a long command. It renders
through a pure `StatusRenderer` (done steps as ✅ lines, the current one as ⏳, a progress
bar for counts) and talks to Discord through a `MessageEditor`, so tests use a recorder
instead of a fake of discord.py.

```python
from discord_bot_core.ui import EmbedField, StatusMessage

status = StatusMessage.for_interaction(interaction, title="🎁 Secret Santa")
await status.start("Request received")
await status.step("Drawing names…")

async with status.progress("Sending messages", total=len(people)) as sending:
    for person in people:
        ok = await deliver(person)
        await sending.advance()

await status.finish(
    summary=[
        EmbedField("Participants", str(len(people)), True),
        EmbedField("Delivered", str(ok_count), True),
        EmbedField("Failed", str(failed_count), True),
    ],
)
```

- **Ephemeral by default, deferred correctly.** `for_interaction` uses
  `response.send_message(..., ephemeral=True)` when the interaction is unanswered and
  `edit_original_response` when it was deferred; it never calls the response twice.
- **Throttled.** `advance()` updates the state at once but edits at most every
  `min_edit_interval` seconds (default 1 s); `start`, `step`, `finish` and `fail` always
  flush. The first and last edits are never dropped. Inject `clock` and `sleep` in tests
  to make this instant and deterministic.
- **Serialised.** An `asyncio.Lock` keeps edits ordered, so a late progress edit cannot
  overwrite the final one. After `finish`/`fail` any further call raises `RuntimeError`.
- **Cosmetic failures do not fail the command.** If an edit raises
  `discord.HTTPException` (for example the 15-minute interaction token expired), it is
  logged at WARNING once and editing stops; the command keeps running.
- **No sensitive data.** The helper renders only what it is given. Put counts in the
  steps, never private data (Secret Santa: never who gives to whom).

`fail(text)` shows a final error embed on the same message for a controlled failure;
unexpected errors still go through the error handler.

## Views and modals

```python
import discord
from discord_bot_core.ui import BaseView, SingleUserView


class Confirm(BaseView):
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message("Confirmed", ephemeral=True)
        self.stop()


view = SingleUserView(interaction.user.id)
await view.send(interaction, embed=some_embed)
```

- `BaseView.send(interaction, **kwargs)` replies with the view attached (through the
  response or the followup) and remembers the interaction.
- `on_timeout` clears the components by editing the message with `view=None`; failures
  (the message is gone or the token expired) are logged at DEBUG. Pass
  `clear_on_timeout=False` to keep them.
- `timeout` is capped at 14 minutes (`ValueError` above) because the edit token lives 15.
- `on_error` delegates to `interaction.client.error_handler.handle(...)`, so a failing
  button gets the same ephemeral reply and logging as a failing command. `BaseModal` does
  the same for modals.
- `SingleUserView(user_id, ...)` compares `interaction.user.id` (works in DMs and guilds)
  and answers other users with an ephemeral "This menu belongs to someone else."
- Views hold no database session and no repository: a session must not outlive the
  command. A callback that needs the database opens its own unit of work through
  `bot.database.transaction()` — a separate transaction from the command's.
- No persistent views in v0.1.0; they need stable `custom_id`s and a `setup_hook`
  registration.

## Testing

`StatusMessage` takes a `MessageEditor`, so tests use a recording editor, no fake of
discord.py internals. See the [testing guide](testing.md#statusmessage-with-a-recording-editor)
for the recorder and the injected clock.

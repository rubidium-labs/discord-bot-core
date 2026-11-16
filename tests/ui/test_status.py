"""Tests for the status message: rendering, throttling, ordering and errors."""

import logging

import discord
import pytest

from discord_bot_core.testing import FakeInteraction, FakeUser
from discord_bot_core.ui.status import (
    DONE_PREFIX,
    PENDING_PREFIX,
    InteractionEditor,
    StatusMessage,
    StatusRenderer,
)
from discord_bot_core.ui.theme import DEFAULT_THEME


class RecordingEditor:
    """A ``MessageEditor`` that records every embed it is given."""

    def __init__(self) -> None:
        self.embeds: list[discord.Embed] = []

    async def send(self, embed: discord.Embed) -> None:
        self.embeds.append(embed)

    async def edit(self, embed: discord.Embed) -> None:
        self.embeds.append(embed)


class FakeClock:
    """A controllable clock."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_status(editor: RecordingEditor, clock: FakeClock) -> StatusMessage:
    async def no_sleep(_: float) -> None:
        return None

    return StatusMessage(editor, title="Job", clock=clock, sleep=no_sleep)


def test_renderer_done_and_current_lines() -> None:
    renderer = StatusRenderer("Job")
    embed = renderer.render(steps=["Received"], current="Working")
    assert embed.title == "Job"
    assert embed.colour == DEFAULT_THEME.info
    assert embed.description == f"{DONE_PREFIX} Received\n{PENDING_PREFIX} Working"


def test_renderer_progress_bar() -> None:
    renderer = StatusRenderer("Job", bar_width=10)
    embed = renderer.render(progress=("Sending", 3, 10))
    assert embed.description is not None
    assert "Sending… 3/10" in embed.description
    assert "███░░░░░░░" in embed.description


def test_renderer_final_success_and_error() -> None:
    renderer = StatusRenderer("Job")
    assert renderer.render(text="Done", final="success").colour == (
        DEFAULT_THEME.success
    )
    assert renderer.render(text="Oops", final="error").colour == DEFAULT_THEME.error


async def test_flow_matches_recording_example() -> None:
    editor = RecordingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)

    await status.start("Received")
    await status.step("Working…")
    await status.finish(text="Done")

    assert len(editor.embeds) == 3
    assert "Done" in (editor.embeds[-1].description or "")


async def test_throttle_few_edits_within_interval() -> None:
    editor = RecordingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)
    await status.start("Received")
    before = len(editor.embeds)

    async with status.progress("Sending", total=100) as progress:
        for _ in range(50):
            await progress.advance()

    assert len(editor.embeds) - before <= 2


async def test_finish_always_flushes() -> None:
    editor = RecordingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)
    await status.start("Received")
    async with status.progress("Sending", total=100) as progress:
        await progress.advance()
    await status.finish(text="Done")
    assert "Done" in (editor.embeds[-1].description or "")


async def test_first_and_last_never_dropped() -> None:
    editor = RecordingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)
    await status.start("Received")
    async with status.progress("Sending", total=2) as progress:
        await progress.advance()
        await progress.advance()
    assert editor.embeds[0].description is not None
    assert "Received" in editor.embeds[0].description
    assert "2/2" in (editor.embeds[-1].description or "")


async def test_late_progress_after_finish_raises() -> None:
    editor = RecordingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)
    await status.start("Received")
    progress = status.progress("Sending", total=2)
    await status.finish(text="Done")
    final = editor.embeds[-1]

    with pytest.raises(RuntimeError):
        await progress.advance()

    assert editor.embeds[-1] is final
    assert "Done" in (editor.embeds[-1].description or "")


async def test_calls_after_fail_raise() -> None:
    editor = RecordingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)
    await status.start("Received")
    await status.fail("Broken")

    with pytest.raises(RuntimeError):
        await status.step("More")
    with pytest.raises(RuntimeError):
        await status.finish(text="Done")


async def test_http_exception_stops_editing(caplog: pytest.LogCaptureFixture) -> None:
    class FailingEditor(RecordingEditor):
        async def edit(self, embed: discord.Embed) -> None:
            raise discord.HTTPException(_FakeResponse(), "boom")

    editor = FailingEditor()
    clock = FakeClock()
    status = make_status(editor, clock)
    await status.start("Received")

    with caplog.at_level(logging.WARNING):
        await status.step("Working")
        await status.step("Still working")
        await status.finish(text="Done")

    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert len(editor.embeds) == 1


class _FakeResponse:
    status = 500
    reason = "boom"


async def test_interaction_editor_unanswered_ephemeral() -> None:
    interaction = FakeInteraction()
    editor = InteractionEditor(interaction)
    await editor.send(discord.Embed(title="x"))

    sent = interaction.response.sent[0]
    assert sent.ephemeral is True
    assert sent.embeds


async def test_interaction_editor_deferred_edits_original() -> None:
    interaction = FakeInteraction()
    edits: list[discord.Embed] = []

    async def edit_original_response(**kwargs: object) -> None:
        edits.append(kwargs["embed"])  # type: ignore[arg-type]

    interaction.edit_original_response = edit_original_response  # type: ignore[attr-defined]
    await interaction.response.send_message("deferred")
    editor = InteractionEditor(interaction)
    await editor.send(discord.Embed(title="x"))

    assert len(edits) == 1
    assert len(interaction.response.sent) == 1


async def test_for_interaction_uses_editor() -> None:
    interaction = FakeInteraction()
    status = StatusMessage.for_interaction(interaction, title="Job")
    await status.start("Received")
    assert interaction.response.sent[0].embeds


def test_single_user_ids() -> None:
    interaction = FakeInteraction(user=FakeUser(id=7))
    assert interaction.user.id == 7

"""The full §12.5 table: the per-command session from ``@transactional``."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

import discord
import pytest
from discord import app_commands
from doubles import FakeDatabase, Repository
from forward_ref import command as forward_ref_command
from future_cog import FutureCog

from discord_bot_core.commands import get_session, transactional
from discord_bot_core.commands.transactional import SESSION_KEY
from discord_bot_core.errors import (
    DatabaseNotConfiguredError,
    ErrorHandler,
    NoActiveSessionError,
    UserFacingError,
)
from discord_bot_core.testing import FakeClient, FakeInteraction


class Settings:
    error_log_channel_id: int | None = None


def _interaction(db: Any) -> FakeInteraction:
    return FakeInteraction(client=FakeClient(database=db))


async def test_commit_on_success() -> None:
    db = FakeDatabase()

    @transactional
    async def command(interaction: Any) -> None:
        Repository(get_session(interaction)).add("row")

    interaction = _interaction(db)
    await command(interaction)

    session = db.sessions[0]
    assert session.calls == ["commit", "close"]
    assert session.closed
    assert session.rows == ["row"]


async def test_rollback_on_exception() -> None:
    db = FakeDatabase()

    @transactional
    async def command(interaction: Any) -> None:
        Repository(get_session(interaction)).add("row")
        raise RuntimeError("boom")

    interaction = _interaction(db)
    with pytest.raises(RuntimeError, match="boom"):
        await command(interaction)

    session = db.sessions[0]
    assert session.calls == ["rollback", "close"]
    assert session.closed


async def test_rollback_on_user_facing_error() -> None:
    db = FakeDatabase()

    @transactional
    async def command(interaction: Any) -> None:
        Repository(get_session(interaction)).add("row")
        raise UserFacingError("Not enough participants.")

    interaction = _interaction(db)
    with pytest.raises(UserFacingError):
        await command(interaction)

    assert db.sessions[0].calls == ["rollback", "close"]


async def test_no_commit_after_rollback() -> None:
    db = FakeDatabase()

    @transactional
    async def command(interaction: Any) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await command(_interaction(db))

    calls = db.sessions[0].calls
    assert "commit" not in calls
    assert calls == ["rollback", "close"]


async def test_two_repositories_one_transaction() -> None:
    db = FakeDatabase()
    seen: list[Any] = []

    @transactional
    async def command(interaction: Any) -> None:
        a = Repository(get_session(interaction))
        b = Repository(get_session(interaction))
        seen.extend([a._session, b._session])
        a.add("a")
        b.add("b")

    await command(_interaction(db))

    assert seen[0] is seen[1]
    assert db.sessions[0].rows == ["a", "b"]


async def test_partial_progress_with_early_commit() -> None:
    db = FakeDatabase()
    committed_before_failure: list[list[object]] = []

    @transactional
    async def command(interaction: Any) -> None:
        session = get_session(interaction)
        session.add("first")
        await session.commit()
        committed_before_failure.append(list(session.rows))
        session.add("second")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await command(_interaction(db))

    assert committed_before_failure == [["first"]]
    assert db.sessions[0].calls == ["commit", "rollback", "close"]


def test_session_not_an_option() -> None:
    class Cog:
        @app_commands.command(name="secret-santa", description="Draw names.")
        @app_commands.describe(participants="Mentions of the participants")
        @transactional
        async def secret_santa(
            self, interaction: discord.Interaction, participants: str
        ) -> None: ...

    command = Cog.secret_santa
    assert isinstance(command, app_commands.Command)
    assert [p.name for p in command.parameters] == ["participants"]

    future = FutureCog.future
    assert isinstance(future, app_commands.Command)
    assert [p.name for p in future.parameters] == ["participants"]


def test_session_not_an_option_for_free_function() -> None:
    @app_commands.command(name="free", description="A free function.")
    @transactional
    async def free(interaction: discord.Interaction, count: int) -> None: ...

    assert isinstance(free, app_commands.Command)
    assert [p.name for p in free.parameters] == ["count"]


def test_signature_is_unchanged() -> None:
    async def original(interaction: discord.Interaction, participants: str) -> None: ...

    wrapped = transactional(original)
    assert inspect.signature(wrapped) == inspect.signature(original, eval_str=True)


def test_name_error_falls_back_to_unevaluated_signature() -> None:
    wrapped = transactional(forward_ref_command)
    assert inspect.signature(wrapped) == inspect.signature(forward_ref_command)


def test_non_coroutine_rejected_at_decoration() -> None:
    def sync(interaction: discord.Interaction) -> None: ...

    with pytest.raises(TypeError, match="async"):
        transactional(sync)  # type: ignore[arg-type]


def test_get_session_outside_transaction() -> None:
    with pytest.raises(NoActiveSessionError, match="outside a @transactional command"):
        get_session(_interaction(FakeDatabase()))


async def test_database_not_configured() -> None:
    ran = False

    @transactional
    async def command(interaction: Any) -> None:
        nonlocal ran
        ran = True

    with pytest.raises(DatabaseNotConfiguredError, match="database_url"):
        await command(_interaction(None))

    assert ran is False


async def test_cancellation_rolls_back() -> None:
    db = FakeDatabase()
    started = asyncio.Event()

    @transactional
    async def command(interaction: Any) -> None:
        Repository(get_session(interaction)).add("row")
        started.set()
        await asyncio.sleep(3600)

    task = asyncio.create_task(command(_interaction(db)))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    session = db.sessions[0]
    assert session.calls == ["rollback", "close"]
    assert session.closed


async def test_extras_cleaned() -> None:
    db = FakeDatabase()

    @transactional
    async def ok(interaction: Any) -> None:
        assert SESSION_KEY in interaction.extras

    @transactional
    async def fail(interaction: Any) -> None:
        raise RuntimeError("boom")

    success = _interaction(db)
    await ok(success)
    assert SESSION_KEY not in success.extras

    failure = _interaction(db)
    with pytest.raises(RuntimeError):
        await fail(failure)
    assert SESSION_KEY not in failure.extras


async def test_concurrent_commands_distinct_sessions() -> None:
    db = FakeDatabase()
    sessions: list[Any] = []

    @transactional
    async def ok(interaction: Any) -> None:
        session = get_session(interaction)
        sessions.append(session)
        await asyncio.sleep(0)

    @transactional
    async def fail(interaction: Any) -> None:
        sessions.append(get_session(interaction))
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    results = await asyncio.gather(
        ok(_interaction(db)), fail(_interaction(db)), return_exceptions=True
    )

    assert isinstance(results[1], RuntimeError)
    assert sessions[0] is not sessions[1]
    assert db.sessions[0].calls == ["commit", "close"]
    assert db.sessions[1].calls == ["rollback", "close"]


async def test_commit_failure_propagates() -> None:
    db = FakeDatabase(fail_commit=True)

    @transactional
    async def command(interaction: Any) -> None:
        Repository(get_session(interaction)).add("row")

    with pytest.raises(RuntimeError, match="commit failed"):
        await command(_interaction(db))

    session = db.sessions[0]
    assert session.calls == ["commit", "rollback", "close"]
    assert session.closed


async def test_error_path_end_to_end() -> None:
    handler = ErrorHandler(Settings())
    db = FakeDatabase()

    class HandlerTree(app_commands.CommandTree[Any]):
        async def on_error(
            self,
            interaction: discord.Interaction,
            error: app_commands.AppCommandError,
            /,
        ) -> None:
            await handler.handle(interaction, error)

    tree = HandlerTree.__new__(HandlerTree)

    @app_commands.command(name="secret-santa", description="Draw names.")
    @transactional
    async def command(interaction: discord.Interaction, participants: str) -> None:
        Repository(get_session(interaction)).add("row")
        raise UserFacingError("Not enough participants.")

    assert isinstance(command, app_commands.Command)
    interaction = _interaction(db)
    interaction._state = object()  # type: ignore[attr-defined]
    namespace = app_commands.Namespace(
        interaction,  # type: ignore[arg-type]
        {},
        [{"name": "participants", "type": 3, "value": "Ada, Grace"}],
    )
    with pytest.raises(app_commands.CommandInvokeError) as caught:
        await command._invoke_with_namespace(interaction, namespace)  # type: ignore[arg-type]
    await tree.on_error(interaction, caught.value)  # type: ignore[arg-type]

    assert interaction.response.sent[0].content == "Not enough participants."
    assert interaction.response.sent[0].ephemeral is True
    assert db.sessions[0].calls == ["rollback", "close"]

"""Tests for the error handler: classification, replies, logging and reporting."""

import logging
from dataclasses import dataclass
from typing import Any

import discord
import pytest
from discord import app_commands

from discord_bot_core.errors import ErrorHandler, OwnerOnlyError, UserFacingError
from discord_bot_core.testing import FakeInteraction

GENERIC = "Something went wrong. Error id: `"


@dataclass
class Settings:
    error_log_channel_id: int | None = None


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class RecordingChannel:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> None:
        self.sent.append(kwargs)


class RaisingChannel:
    async def send(self, **kwargs: Any) -> None:
        raise discord.HTTPException(_response(), "boom")


class RaisingResponse:
    def is_done(self) -> bool:
        return False

    async def send_message(self, *args: Any, **kwargs: Any) -> None:
        raise discord.HTTPException(_response(), "expired")


def _response() -> Any:
    return type("Response", (), {"status": 500, "reason": "boom"})()


def _cooldown() -> app_commands.Cooldown:
    return app_commands.Cooldown(1, 10.0)


class FakeTransformer:
    _error_display_name = "member"


def _transformer_error() -> app_commands.TransformerError:
    return app_commands.TransformerError(
        "x",
        discord.AppCommandOptionType.string,
        FakeTransformer(),  # type: ignore[arg-type]
    )


CASES: list[tuple[BaseException, str, int]] = [
    (
        UserFacingError("Not enough participants."),
        "Not enough participants.",
        logging.INFO,
    ),
    (OwnerOnlyError(), "You can't use this command.", logging.INFO),
    (app_commands.CheckFailure(), "You can't use this command.", logging.INFO),
    (
        app_commands.NoPrivateMessage(),
        "This command only works in a server.",
        logging.INFO,
    ),
    (
        app_commands.MissingPermissions(["manage_guild"]),
        "You need the Manage Server permission(s) to use this command.",
        logging.INFO,
    ),
    (
        app_commands.BotMissingPermissions(["send_messages", "embed_links"]),
        "You need the Send Messages and Embed Links permission(s) to use this command.",
        logging.INFO,
    ),
    (
        app_commands.CommandOnCooldown(_cooldown(), 4.4),
        "Try again in 4 s.",
        logging.INFO,
    ),
    (
        app_commands.CommandNotFound("nope", []),
        "This command is out of date, try again in a few minutes.",
        logging.WARNING,
    ),
    (
        app_commands.CommandSignatureMismatch(type("Command", (), {"name": "nope"})()),
        "This command is out of date, try again in a few minutes.",
        logging.WARNING,
    ),
    (
        _transformer_error(),
        "Invalid value for `member`.",
        logging.INFO,
    ),
]


@pytest.mark.parametrize(("error", "message", "level"), CASES)
async def test_classification(
    error: BaseException, message: str, level: int, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    interaction = FakeInteraction()
    handler = ErrorHandler(Settings())

    await handler.handle(interaction, error)

    sent = interaction.response.sent
    assert len(sent) == 1
    assert sent[0].content == message
    assert sent[0].ephemeral is True
    assert not interaction.followup.sent
    assert caplog.records[-1].levelno == level
    assert caplog.records[-1].exc_info is None


async def test_invoke_error_is_unwrapped(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    interaction = FakeInteraction()
    handler = ErrorHandler(Settings())
    wrapped = app_commands.CommandInvokeError(
        type("Command", (), {"name": "test"})(), UserFacingError("Domain says no.")
    )  # type: ignore[arg-type]

    await handler.handle(interaction, wrapped)

    assert interaction.response.sent[0].content == "Domain says no."
    assert next(r for r in caplog.records if r.levelno == logging.INFO).exc_info is None


async def test_unexpected_error_id_in_reply_and_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    interaction = FakeInteraction()
    handler = ErrorHandler(Settings())

    await handler.handle(interaction, RuntimeError("secret detail"))

    content = interaction.response.sent[0].content
    assert content is not None
    assert content.startswith(GENERIC)
    error_id = content.removeprefix(GENERIC).split("`")[0]
    assert len(error_id) == 8
    int(error_id, 16)

    record = next(r for r in caplog.records if r.levelno == logging.ERROR)
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.exc_info[1] is not None
    assert isinstance(record.exc_info[1], RuntimeError)
    assert record.error_id == error_id  # type: ignore[attr-defined]
    assert error_id in record.getMessage()
    assert "secret detail" not in content


async def test_unexpected_dm_guild_id_none(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    interaction = FakeInteraction(guild=None)
    handler = ErrorHandler(Settings())

    await handler.handle(interaction, RuntimeError("boom"))

    assert interaction.guild_id is None
    assert (
        "guild=None"
        in next(r for r in caplog.records if r.levelno == logging.ERROR).getMessage()
    )


async def test_response_done_uses_followup() -> None:
    interaction = FakeInteraction()
    interaction.response._done = True
    handler = ErrorHandler(Settings())

    await handler.handle(interaction, UserFacingError("late"))

    assert not interaction.response.sent
    assert interaction.followup.sent[0].content == "late"
    assert interaction.followup.sent[0].ephemeral is True


async def test_reply_failure_is_swallowed(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    interaction = FakeInteraction()
    interaction.response = RaisingResponse()  # type: ignore[assignment]
    handler = ErrorHandler(Settings())

    await handler.handle(interaction, UserFacingError("x"))

    assert any(
        "Failed to send an error reply" in r.getMessage() for r in caplog.records
    )


async def test_no_report_without_channel() -> None:
    interaction = FakeInteraction()
    handler = ErrorHandler(Settings(error_log_channel_id=None))

    await handler.handle(interaction, RuntimeError("boom"))

    assert interaction.response.sent


async def test_channel_report_embed(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    channel = RecordingChannel()
    client = FakeInteraction().client
    client.channels[42] = channel
    interaction = FakeInteraction(client=client)
    interaction.guild = type("Guild", (), {"id": 7})()
    interaction.guild_id = 7
    handler = ErrorHandler(Settings(error_log_channel_id=42))

    try:
        raise RuntimeError("secret detail")
    except RuntimeError as error:
        await handler.handle(interaction, error)

    assert len(channel.sent) == 1
    embed: discord.Embed = channel.sent[0]["embed"]
    text = embed.to_dict()
    rendered = str(text)
    assert "secret detail" not in rendered
    assert "RuntimeError" in rendered
    assert "/test" in rendered
    assert "test_handler.py" in rendered
    assert "7" in rendered


async def test_channel_report_dm(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    channel = RecordingChannel()
    client = FakeInteraction().client
    client.channels[42] = channel
    handler = ErrorHandler(Settings(error_log_channel_id=42))

    await handler.handle(
        FakeInteraction(client=client, guild=None), RuntimeError("boom")
    )

    embed: discord.Embed = channel.sent[0]["embed"]
    assert "DM" in str(embed.to_dict())


async def test_channel_report_rate_limit() -> None:
    clock = FakeClock()
    channel = RecordingChannel()
    client = FakeInteraction().client
    client.channels[42] = channel
    handler = ErrorHandler(Settings(error_log_channel_id=42), clock=clock)
    interaction = FakeInteraction(client=client)

    await handler.handle(interaction, RuntimeError("one"))
    await handler.handle(interaction, RuntimeError("two"))
    await handler.handle(interaction, RuntimeError("three"))
    assert len(channel.sent) == 1

    clock.now += 61
    await handler.handle(interaction, RuntimeError("four"))
    assert len(channel.sent) == 2
    embed: discord.Embed = channel.sent[1]["embed"]
    assert "2" in str(embed.to_dict())


async def test_channel_missing_is_swallowed(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    handler = ErrorHandler(Settings(error_log_channel_id=99))

    await handler.handle(FakeInteraction(), RuntimeError("boom"))

    assert not any("Failed to report" in r.getMessage() for r in caplog.records)


async def test_channel_send_failure_is_swallowed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="discord_bot_core.errors.handler")
    client = FakeInteraction().client
    client.channels[42] = RaisingChannel()
    handler = ErrorHandler(Settings(error_log_channel_id=42))

    await handler.handle(FakeInteraction(client=client), RuntimeError("boom"))

    assert any("Failed to report" in r.getMessage() for r in caplog.records)


async def test_report_not_sent_for_expected_errors() -> None:
    channel = RecordingChannel()
    client = FakeInteraction().client
    client.channels[42] = channel
    handler = ErrorHandler(Settings(error_log_channel_id=42))

    await handler.handle(FakeInteraction(client=client), UserFacingError("nope"))

    assert not channel.sent

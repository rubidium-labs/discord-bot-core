"""Tests for :class:`discord_bot_core.bot.CoreCommandTree`."""

import logging
from typing import Any

import pytest
from discord import app_commands

from discord_bot_core.bot import CoreBot, CoreCommandTree
from discord_bot_core.settings import CoreSettings
from discord_bot_core.testing import FakeCommand, FakeInteraction


def _settings() -> CoreSettings:
    return CoreSettings(discord_token="token", dev_guild_id=1, _env_file=None)


class RecordingHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, BaseException]] = []

    async def handle(self, interaction: Any, error: BaseException) -> None:
        self.calls.append((interaction, error))


class FakeGuild:
    def __init__(self, guild_id: int) -> None:
        self.id = guild_id


async def test_on_error_delegates_to_error_handler() -> None:
    handler = RecordingHandler()
    bot = CoreBot(_settings(), error_handler=handler)  # type: ignore[arg-type]
    interaction = FakeInteraction(client=bot)
    error = app_commands.CheckFailure("nope")
    await bot.tree.on_error(interaction, error)  # type: ignore[arg-type]
    assert handler.calls == [(interaction, error)]


async def test_interaction_check_logs_name_user_and_guild(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = CoreBot(_settings())
    interaction = FakeInteraction(
        client=bot,
        command=FakeCommand(qualified_name="core sync dev"),
        guild=FakeGuild(42),
    )
    with caplog.at_level(logging.INFO):
        assert await bot.tree.interaction_check(interaction) is True  # type: ignore[arg-type]
    assert "core sync dev" in caplog.text
    assert "user=1" in caplog.text
    assert "guild=42" in caplog.text


async def test_interaction_check_logs_none_guild_in_dm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = CoreBot(_settings())
    interaction = FakeInteraction(client=bot, command=FakeCommand("ping"))
    with caplog.at_level(logging.INFO):
        assert await bot.tree.interaction_check(interaction) is True  # type: ignore[arg-type]
    assert "guild=None" in caplog.text


async def test_interaction_check_never_logs_options(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = CoreBot(_settings())
    interaction = FakeInteraction(client=bot, command=FakeCommand("secret_santa"))
    interaction.data = {"options": [{"name": "participants", "value": "alice,bob"}]}
    with caplog.at_level(logging.INFO):
        await bot.tree.interaction_check(interaction)  # type: ignore[arg-type]
    assert "alice" not in caplog.text
    assert "participants" not in caplog.text


async def test_interaction_check_never_raises() -> None:
    bot = CoreBot(_settings())
    interaction = FakeInteraction(client=bot, command=None)
    assert await bot.tree.interaction_check(interaction) is True  # type: ignore[arg-type]


def test_tree_is_core_command_tree() -> None:
    bot = CoreBot(_settings())
    assert isinstance(bot.tree, CoreCommandTree)

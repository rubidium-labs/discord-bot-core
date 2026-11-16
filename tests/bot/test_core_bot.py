"""Tests for :class:`discord_bot_core.bot.CoreBot`."""

import logging
from typing import Any

import discord
import pytest
from discord.ext import commands

from discord_bot_core.bot import CoreBot, CoreCommandTree
from discord_bot_core.errors import ErrorHandler
from discord_bot_core.settings import CoreSettings
from discord_bot_core.testing import memory_database

TOKEN = "super-secret-token"


def _settings(**overrides: Any) -> CoreSettings:
    values: dict[str, Any] = {
        "discord_token": TOKEN,
        "dev_guild_id": 1,
        "_env_file": None,
    }
    values.update(overrides)
    return CoreSettings(**values)


class FakeDatabase:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


def test_builds_without_network() -> None:
    bot = CoreBot(_settings())
    assert isinstance(bot, commands.Bot)
    assert isinstance(bot.tree, CoreCommandTree)
    assert bot.settings.discord_token.get_secret_value() == TOKEN
    assert bot.database is None
    assert bot.extension_manager is None


def test_default_intents_have_no_privileged_flags() -> None:
    bot = CoreBot(_settings())
    assert bot.intents == discord.Intents.default()
    assert not bot.intents.members
    assert not bot.intents.message_content


def test_given_intents_are_used() -> None:
    intents = discord.Intents.default()
    intents.members = True
    bot = CoreBot(_settings(), intents=intents)
    assert bot.intents.members is True


def test_no_on_ready_handler() -> None:
    assert "on_ready" not in CoreBot.__dict__
    bot = CoreBot(_settings())
    assert len(bot.extra_events.get("on_ready", [])) == 0


async def test_setup_hook_logs_database_not_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = CoreBot(_settings())
    try:
        with caplog.at_level(logging.INFO):
            await bot.setup_hook()
        assert "No database configured" in caplog.text
    finally:
        await bot.close()


async def test_setup_hook_logs_database_configured_without_url(
    caplog: pytest.LogCaptureFixture,
) -> None:
    url = "postgresql+asyncpg://user:password@localhost/db"
    bot = CoreBot(_settings(database_url=url), database=FakeDatabase())
    try:
        with caplog.at_level(logging.INFO):
            await bot.setup_hook()
        assert "Database configured" in caplog.text
        assert "password" not in caplog.text
        assert url not in caplog.text
    finally:
        await bot.close()


async def test_setup_hook_calls_configure() -> None:
    called: list[bool] = []

    class RecordingBot(CoreBot):
        async def configure(self) -> None:
            called.append(True)

    bot = RecordingBot(_settings())
    try:
        await bot.setup_hook()
        assert called == [True]
    finally:
        await bot.close()


async def test_close_runs_cleanups_in_order_and_disposes_database() -> None:
    database = FakeDatabase()
    bot = CoreBot(_settings(), database=database)
    order: list[str] = []

    async def first() -> None:
        order.append("first")

    async def second() -> None:
        order.append("second")

    bot.register_cleanup(first)
    bot.register_cleanup(second)
    await bot.close()
    assert order == ["first", "second"]
    assert database.disposed is True


def test_launch_configures_logging_and_passes_log_handler_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = CoreBot(_settings(log_level="WARNING", environment="dev"))
    calls: dict[str, Any] = {}

    def fake_run(token: str, **kwargs: Any) -> None:
        calls["token"] = token
        calls["kwargs"] = kwargs

    monkeypatch.setattr(bot, "run", fake_run)
    bot.launch()
    assert calls["token"] == TOKEN
    assert calls["kwargs"] == {"log_handler": None}
    assert logging.getLogger().level == logging.WARNING


async def test_wiring_uses_real_database_and_settings() -> None:
    settings = _settings()
    async with memory_database() as database:
        bot = CoreBot(settings, database=database)
        try:
            assert bot.database is database
            assert bot.settings is settings
            assert isinstance(bot.error_handler, ErrorHandler)
        finally:
            await bot.close()

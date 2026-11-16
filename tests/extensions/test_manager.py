"""Tests for the extension manager."""

from __future__ import annotations

import logging

import pytest
from stub_bot import StubBot

from discord_bot_core.errors import UserFacingError
from discord_bot_core.extensions import ExtensionManager, LoadReport

PACKAGE = "tests.extensions.fixture_pkg"
GOOD = f"{PACKAGE}.good"
FAILING = f"{PACKAGE}.failing"
SUBPKG = f"{PACKAGE}.subpkg"
NO_SETUP = f"{PACKAGE}.no_setup"


def manager(bot: StubBot) -> ExtensionManager:
    return ExtensionManager(bot, PACKAGE)


def test_available_lists_discovered(bot: StubBot) -> None:
    assert manager(bot).available() == [FAILING, GOOD, NO_SETUP, SUBPKG]


async def test_loaded_and_unloaded(bot: StubBot) -> None:
    ext = manager(bot)
    assert ext.loaded() == []
    assert ext.unloaded() == ext.available()

    await ext.load("good")

    assert ext.loaded() == [GOOD]
    assert GOOD not in ext.unloaded()


def test_resolve_short_and_full(bot: StubBot) -> None:
    ext = manager(bot)
    assert ext.resolve("good") == GOOD
    assert ext.resolve(GOOD) == GOOD


def test_resolve_unknown_raises(bot: StubBot) -> None:
    with pytest.raises(UserFacingError):
        manager(bot).resolve("missing")


@pytest.mark.parametrize("name", ["os", "os.path", "discord", "discord.ext"])
def test_load_outside_package_is_rejected(bot: StubBot, name: str) -> None:
    with pytest.raises(UserFacingError):
        manager(bot).resolve(name)


async def test_load_outside_package_raises(bot: StubBot) -> None:
    with pytest.raises(UserFacingError):
        await manager(bot).load("os")
    assert bot.extensions == {}


async def test_load_already_loaded(bot: StubBot) -> None:
    ext = manager(bot)
    await ext.load("good")
    with pytest.raises(UserFacingError, match="already loaded"):
        await ext.load("good")


async def test_unload_not_loaded(bot: StubBot) -> None:
    with pytest.raises(UserFacingError, match="not loaded"):
        await manager(bot).unload("good")


async def test_load_missing_module(bot: StubBot) -> None:
    ext = ExtensionManager(bot, PACKAGE)
    ext.resolve = lambda name: f"{PACKAGE}.does_not_exist"  # type: ignore[method-assign]
    with pytest.raises(UserFacingError, match="not found"):
        await ext.load("does_not_exist")


async def test_load_no_entry_point(bot: StubBot) -> None:
    with pytest.raises(UserFacingError, match="setup"):
        await manager(bot).load("no_setup")


async def test_load_failure_logs_traceback(
    bot: StubBot, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        with pytest.raises(UserFacingError, match="failed to load"):
            await manager(bot).load("failing")

    record = next(r for r in caplog.records if r.levelno == logging.WARNING)
    assert record.exc_info is not None
    assert FAILING in record.getMessage()


async def test_load_all_continues_after_failure(bot: StubBot) -> None:
    report = await manager(bot).load_all()

    assert isinstance(report, LoadReport)
    assert GOOD in report.loaded
    assert SUBPKG in report.loaded
    assert FAILING in report.failed
    assert NO_SETUP in report.failed
    assert "boom" not in report.failed[FAILING]


async def test_reload_calls_unload_and_load(bot: StubBot) -> None:
    ext = manager(bot)
    await ext.load("good")
    await ext.reload("good")
    assert GOOD in bot.extensions
    assert ext.loaded() == [GOOD]

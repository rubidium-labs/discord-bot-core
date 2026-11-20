"""Tests for the views and modals."""

import logging

import discord
import pytest

from discord_bot_core.testing import FakeClient, FakeInteraction, FakeUser
from discord_bot_core.ui.views import (
    MAX_TIMEOUT,
    OTHER_USER_MESSAGE,
    BaseModal,
    BaseView,
    SingleUserView,
)


class RecordingHandler:
    """An error handler that records what it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, BaseException]] = []

    async def handle(
        self, interaction: discord.Interaction, error: BaseException
    ) -> None:
        self.calls.append((interaction, error))


def test_timeout_cap() -> None:
    with pytest.raises(ValueError):
        BaseView(timeout=MAX_TIMEOUT + 1)
    BaseView(timeout=MAX_TIMEOUT)


async def test_on_timeout_clears_components() -> None:
    interaction = FakeInteraction()
    edits: list[object] = []

    async def edit_original_response(**kwargs: object) -> None:
        edits.append(kwargs.get("view"))

    interaction.edit_original_response = edit_original_response  # type: ignore[attr-defined]
    view = BaseView()
    await view.send(interaction)
    await view.on_timeout()

    assert edits == [None]


async def test_on_timeout_failure_is_debug_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    interaction = FakeInteraction()

    async def edit_original_response(**kwargs: object) -> None:
        raise RuntimeError("gone")

    interaction.edit_original_response = edit_original_response  # type: ignore[attr-defined]
    view = BaseView()
    await view.send(interaction)
    with caplog.at_level(logging.DEBUG):
        await view.on_timeout()
    assert any(record.levelno == logging.DEBUG for record in caplog.records)


async def test_send_attaches_view() -> None:
    interaction = FakeInteraction()
    view = BaseView()
    await view.send(interaction, content="hi")
    sent = interaction.response.sent[0]
    assert sent.view is view
    assert sent.content == "hi"


async def test_single_user_view_owner() -> None:
    view = SingleUserView(user_id=7)
    interaction = FakeInteraction(user=FakeUser(id=7))
    assert await view.interaction_check(interaction) is True


async def test_single_user_view_other() -> None:
    view = SingleUserView(user_id=7)
    interaction = FakeInteraction(user=FakeUser(id=8))
    assert await view.interaction_check(interaction) is False
    sent = interaction.response.sent[0]
    assert sent.ephemeral is True
    assert sent.content == OTHER_USER_MESSAGE


async def test_single_user_view_other_is_translated() -> None:
    from typing import Any

    from discord_bot_core.i18n import CORE_CATALOG

    class FrenchInteraction(FakeInteraction):
        async def translate(self, string: Any, **kwargs: Any) -> str | None:
            return CORE_CATALOG.get(string.message, discord.Locale.french)

    view = SingleUserView(user_id=7)
    interaction = FrenchInteraction(user=FakeUser(id=8))
    assert await view.interaction_check(interaction) is False
    assert (
        interaction.response.sent[0].content
        == "Ce menu appartient à quelqu'un d'autre."
    )


async def test_view_on_error_delegates() -> None:
    handler = RecordingHandler()
    interaction = FakeInteraction(client=FakeClient(error_handler=handler))
    view = BaseView()
    error = RuntimeError("boom")
    await view.on_error(interaction, error, None)  # type: ignore[arg-type]
    assert handler.calls == [(interaction, error)]


async def test_modal_on_error_delegates() -> None:
    handler = RecordingHandler()
    interaction = FakeInteraction(client=FakeClient(error_handler=handler))
    modal = BaseModal(title="Test")
    error = RuntimeError("boom")
    await modal.on_error(interaction, error)
    assert handler.calls == [(interaction, error)]


def test_modal_is_discord_modal() -> None:
    assert issubclass(BaseModal, discord.ui.Modal)

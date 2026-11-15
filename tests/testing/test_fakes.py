"""Tests for the testing fakes."""

from discord_bot_core.testing import FakeClient, FakeInteraction


async def test_records_sends_in_order() -> None:
    interaction = FakeInteraction()

    await interaction.response.send_message("first", ephemeral=True)
    await interaction.followup.send("second", embed=object())

    assert interaction.response.sent[0].content == "first"
    assert interaction.response.sent[0].ephemeral is True
    assert interaction.response.sent[0].kind == "response"
    assert interaction.followup.sent[0].content == "second"
    assert interaction.followup.sent[0].kind == "followup"
    assert interaction.followup.sent[0].embeds


async def test_response_is_done_after_send() -> None:
    interaction = FakeInteraction()
    assert not interaction.response.is_done()
    await interaction.response.send_message("hi")
    assert interaction.response.is_done()


def test_guild_id_from_guild() -> None:
    guild = type("Guild", (), {"id": 5})()
    interaction = FakeInteraction(guild=guild)
    assert interaction.guild_id == 5


def test_dm_has_no_guild_id() -> None:
    interaction = FakeInteraction(guild=None)
    assert interaction.guild_id is None
    assert interaction.guild is None


def test_client_extras() -> None:
    client = FakeClient(database="db")
    assert client.extras == {"database": "db"}
    assert client.database == "db"  # type: ignore[attr-defined]

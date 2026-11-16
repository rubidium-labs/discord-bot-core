"""The ``owner_only`` check: owners pass, everyone else gets ``OwnerOnlyError``."""

from typing import Any

import pytest

from discord_bot_core.commands import owner_only
from discord_bot_core.errors import OwnerOnlyError
from discord_bot_core.testing import FakeClient, FakeInteraction


class OwnerClient(FakeClient):
    def __init__(self, owner_id: int) -> None:
        super().__init__()
        self.owner_id = owner_id

    async def is_owner(self, user: Any, /) -> bool:
        return user.id == self.owner_id


async def test_owner_passes() -> None:
    interaction = FakeInteraction(client=OwnerClient(owner_id=1))
    assert await owner_only()(interaction) is True  # type: ignore[arg-type]


async def test_non_owner_raises() -> None:
    interaction = FakeInteraction(client=OwnerClient(owner_id=99))
    with pytest.raises(OwnerOnlyError):
        await owner_only()(interaction)  # type: ignore[arg-type]

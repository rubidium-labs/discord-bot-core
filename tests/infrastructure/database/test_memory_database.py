"""Tests for testing.memory_database()."""

from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from discord_bot_core.infrastructure.database import Base
from discord_bot_core.testing import memory_database


class Widget(Base):
    __tablename__ = "widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


async def test_memory_database_round_trip() -> None:
    async with memory_database() as db:
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with db.transaction() as session:
            session.add(Widget(id=1, name="gear"))

        async with db.transaction() as session:
            result = await session.execute(select(Widget).where(Widget.id == 1))
            assert result.scalar_one().name == "gear"

    Base.metadata.remove(Widget.__table__)

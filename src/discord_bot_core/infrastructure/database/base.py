"""The declarative base every application's models inherit from.

The library defines no table; ``Base`` only carries the metadata with a naming
convention, so constraint names are deterministic and Alembic can drop and alter
them (in particular with SQLite batch mode).
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""The naming templates applied to indexes and constraints."""


class Base(DeclarativeBase):
    """Declarative base for application models.

    Example:
        >>> class Draw(Base):
        ...     __tablename__ = "draws"
        ...     id: Mapped[int] = mapped_column(primary_key=True)
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

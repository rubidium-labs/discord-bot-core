"""The base every repository inherits from.

Repositories hold the session of the current unit of work and never commit: they
``add``, ``flush`` and ``execute``; the transaction decides commit and rollback.
There is deliberately no generic CRUD, which would hide the queries.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """A repository bound to one session.

    Attributes:
        _session: The session shared by every repository of the unit of work.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Store the session.

        Args:
            session: The session of the current transaction.
        """
        self._session = session

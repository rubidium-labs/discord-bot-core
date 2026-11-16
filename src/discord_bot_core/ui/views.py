"""Views and modals: the base classes an application's UI components extend.

Views hold no database session and no repository; a callback that needs the
database opens its own unit of work. No persistent views are provided in v0.1.0.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import discord

logger = logging.getLogger(__name__)

MAX_TIMEOUT = 14 * 60.0
OTHER_USER_MESSAGE = "This menu belongs to someone else."

__all__ = [
    "MAX_TIMEOUT",
    "OTHER_USER_MESSAGE",
    "BaseModal",
    "BaseView",
    "SingleUserView",
]


class _ErrorHandler(Protocol):
    """The part of the bot's error handler the views use."""

    async def handle(
        self, interaction: discord.Interaction, error: BaseException
    ) -> None:
        """Handle ``error`` raised while processing ``interaction``."""
        ...


class _ErrorClient(Protocol):
    """The part of the client the views read."""

    error_handler: _ErrorHandler


class BaseView(discord.ui.View):
    """A view that delegates errors to the bot's error handler and cleans up.

    Example:
        >>> class Confirm(BaseView):
        ...     @discord.ui.button(label="OK")
        ...     async def ok(self, interaction, button):  # doctest: +SKIP
        ...         await interaction.response.send_message("Done")
    """

    def __init__(
        self, *, timeout: float = 180.0, clear_on_timeout: bool = True
    ) -> None:
        """Create the view.

        Args:
            timeout: Seconds before the view stops listening; at most 14 minutes,
                because the interaction token lives 15.
            clear_on_timeout: Whether to clear the components when the view times
                out.

        Raises:
            ValueError: If ``timeout`` is greater than 14 minutes.
        """
        if timeout > MAX_TIMEOUT:
            msg = f"timeout must be at most {MAX_TIMEOUT} seconds (14 minutes)"
            raise ValueError(msg)
        super().__init__(timeout=timeout)
        self.clear_on_timeout = clear_on_timeout
        self._message_interaction: discord.Interaction | None = None

    async def send(self, interaction: discord.Interaction, **kwargs: Any) -> None:
        """Send the view attached to a message.

        Remembers the interaction so :meth:`on_timeout` can clear the components.

        Args:
            interaction: The interaction to reply to.
            **kwargs: Passed to ``response.send_message`` or ``followup.send``.
        """
        self._message_interaction = interaction
        if interaction.response.is_done():
            await interaction.followup.send(view=self, **kwargs)
        else:
            await interaction.response.send_message(view=self, **kwargs)

    async def on_timeout(self) -> None:
        """Clear the components when the view times out.

        Edits through the stored interaction; failures (the message is gone or the
        token expired) are logged at DEBUG.
        """
        if not self.clear_on_timeout:
            return
        interaction = self._message_interaction
        if interaction is None:
            return
        try:
            await interaction.edit_original_response(view=None)
        except Exception as exc:
            logger.debug("Failed to clear view components on timeout: %s", exc)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Delegate an item's error to the bot's error handler.

        Args:
            interaction: The interaction that led to the failure.
            error: The exception raised.
            item: The item that failed.
        """
        client: _ErrorClient = interaction.client  # type: ignore[assignment]
        await client.error_handler.handle(interaction, error)


class SingleUserView(BaseView):
    """A view only its owner may use.

    Attributes:
        user_id: The id of the user the view belongs to.
    """

    def __init__(self, user_id: int, *, timeout: float = 180.0, **kwargs: Any) -> None:
        """Create the view.

        Args:
            user_id: The id of the user the view belongs to.
            timeout: Seconds before the view stops listening; at most 14 minutes.
            **kwargs: Passed to :class:`BaseView`.
        """
        super().__init__(timeout=timeout, **kwargs)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        """Allow only the owner; tell others the menu is not theirs.

        Args:
            interaction: The interaction to check.

        Returns:
            ``True`` for the owner, ``False`` otherwise.
        """
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(OTHER_USER_MESSAGE, ephemeral=True)
        return False


class BaseModal(discord.ui.Modal):
    """A modal that delegates errors to the bot's error handler."""

    async def on_error(  # type: ignore[override]
        self,
        interaction: discord.Interaction,
        error: Exception,
        /,
    ) -> None:
        """Delegate an error to the bot's error handler.

        Args:
            interaction: The interaction that led to the failure.
            error: The exception raised.
        """
        client: _ErrorClient = interaction.client  # type: ignore[assignment]
        await client.error_handler.handle(interaction, error)

"""The single handler for errors raised by commands, views and modals.

``CoreCommandTree.on_error`` (and the UI kit's ``BaseView``/``BaseModal``) delegate
here. The handler classifies the error, replies ephemerally, logs it and — for
unexpected errors only — optionally reports it to a log channel. It never raises.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import discord
from discord import app_commands

from discord_bot_core.errors.exceptions import OwnerOnlyError, UserFacingError
from discord_bot_core.settings import CoreSettings

logger = logging.getLogger(__name__)

GENERIC_MESSAGE = "Something went wrong. Error id: `{error_id}`."
OUT_OF_DATE_MESSAGE = "This command is out of date, try again in a few minutes."
CHECK_FAILURE_MESSAGE = "You can't use this command."
NO_PRIVATE_MESSAGE = "This command only works in a server."

_REPORT_WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class Outcome:
    """The result of classifying an error.

    Attributes:
        message: The text shown to the user.
        level: The log level for the error.
        expected: ``True`` for errors the handler understands (no traceback, no
            report); ``False`` for the unexpected path.
    """

    message: str
    level: int
    expected: bool


def _permissions_message(names: list[str]) -> str:
    readable = [
        name.replace("_", " ").replace("guild", "server").title() for name in names
    ]
    if len(readable) == 1:
        joined = readable[0]
    else:
        joined = ", ".join(readable[:-1]) + " and " + readable[-1]
    return f"You need the {joined} permission(s) to use this command."


def _last_frame_location(exc: BaseException) -> str:
    frame = exc.__traceback__
    if frame is None:
        return "<unknown>"
    while frame.tb_next is not None:
        frame = frame.tb_next
    code = frame.tb_frame.f_code
    return f"{code.co_filename}:{frame.tb_lineno}"


def _command_name(interaction: discord.Interaction) -> str:
    command = interaction.command
    return command.qualified_name if command is not None else "<unknown>"


class ErrorHandler:
    """Classify and answer errors from commands, views and modals.

    Example:
        >>> handler = ErrorHandler(settings)  # doctest: +SKIP
        >>> await handler.handle(interaction, error)  # doctest: +SKIP
    """

    def __init__(
        self,
        settings: CoreSettings,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the handler.

        Args:
            settings: The bot's settings; only ``error_log_channel_id`` is read, and
                the report channel is used only when it is set.
            clock: Monotonic clock used for the report rate limit; injectable for
                tests.
        """
        self._settings = settings
        self._clock = clock
        self._last_report: dict[tuple[str, str], float] = {}
        self._suppressed: dict[tuple[str, str], int] = {}

    async def handle(
        self, interaction: discord.Interaction, error: BaseException
    ) -> None:
        """Handle ``error`` raised while processing ``interaction``.

        Unwraps :class:`discord.app_commands.CommandInvokeError`, classifies the
        original exception, replies ephemerally and logs it. Never raises.

        Args:
            interaction: The interaction whose command failed.
            error: The exception, possibly a ``CommandInvokeError`` wrapper.
        """
        original = (
            error.original
            if isinstance(error, app_commands.CommandInvokeError)
            else error
        )
        error_id = secrets.token_hex(4)
        outcome = self.classify(original, error_id)
        if outcome.expected:
            logger.log(outcome.level, "%s", original)
        else:
            name = _command_name(interaction)
            logger.error(
                "Unhandled error %s in /%s user=%s guild=%s channel=%s",
                error_id,
                name,
                interaction.user.id,
                interaction.guild_id,
                interaction.channel_id,
                exc_info=original,
                extra={"error_id": error_id},
            )
            await self._report(interaction, original, error_id, name)
        await self._reply(interaction, outcome.message)

    def classify(self, error: BaseException, error_id: str | None = None) -> Outcome:
        """Map an unwrapped exception to the message, log level and path.

        Args:
            error: The original exception (not a ``CommandInvokeError``).
            error_id: The id to embed in the generic message; generated when omitted.

        Returns:
            The outcome for this error.
        """
        if isinstance(error, UserFacingError):
            return Outcome(error.message, logging.INFO, expected=True)
        if isinstance(error, OwnerOnlyError):
            return Outcome(CHECK_FAILURE_MESSAGE, logging.INFO, expected=True)
        if isinstance(error, app_commands.NoPrivateMessage):
            return Outcome(NO_PRIVATE_MESSAGE, logging.INFO, expected=True)
        if isinstance(
            error, (app_commands.MissingPermissions, app_commands.BotMissingPermissions)
        ):
            return Outcome(
                _permissions_message(error.missing_permissions),
                logging.INFO,
                expected=True,
            )
        if isinstance(error, app_commands.CommandOnCooldown):
            return Outcome(
                f"Try again in {round(error.retry_after)} s.",
                logging.INFO,
                expected=True,
            )
        if isinstance(
            error, (app_commands.CommandNotFound, app_commands.CommandSignatureMismatch)
        ):
            return Outcome(OUT_OF_DATE_MESSAGE, logging.WARNING, expected=True)
        if isinstance(error, app_commands.TransformerError):
            return Outcome(
                f"Invalid value for `{error.transformer._error_display_name}`.",
                logging.INFO,
                expected=True,
            )
        if isinstance(error, app_commands.CheckFailure):
            return Outcome(CHECK_FAILURE_MESSAGE, logging.INFO, expected=True)
        if error_id is None:
            error_id = secrets.token_hex(4)
        return Outcome(GENERIC_MESSAGE.format(error_id=error_id), logging.ERROR, False)

    async def _reply(self, interaction: discord.Interaction, message: str) -> None:
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception:
            logger.exception("Failed to send an error reply")

    async def _report(
        self,
        interaction: discord.Interaction,
        error: BaseException,
        error_id: str,
        name: str,
    ) -> None:
        channel_id = self._settings.error_log_channel_id
        if channel_id is None:
            return
        key = (name, type(error).__name__)
        now = self._clock()
        last = self._last_report.get(key)
        if last is not None and now - last < _REPORT_WINDOW_SECONDS:
            self._suppressed[key] = self._suppressed.get(key, 0) + 1
            return
        suppressed = self._suppressed.pop(key, 0)
        self._last_report[key] = now
        try:
            channel = await self._get_channel(interaction.client, channel_id)
            if channel is None:
                return
            await channel.send(
                embed=self._build_embed(interaction, error, error_id, name, suppressed)
            )
        except Exception:
            logger.exception("Failed to report error %s to the log channel", error_id)

    async def _get_channel(self, client: Any, channel_id: int) -> Any:
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except Exception:
                logger.exception("Failed to fetch error log channel %s", channel_id)
                return None
        return channel

    def _build_embed(
        self,
        interaction: discord.Interaction,
        error: BaseException,
        error_id: str,
        name: str,
        suppressed: int,
    ) -> discord.Embed:
        guild = str(interaction.guild_id) if interaction.guild_id is not None else "DM"
        embed = discord.Embed(title=f"Error {error_id}", colour=discord.Colour.red())
        embed.add_field(name="Command", value=f"/{name}", inline=True)
        embed.add_field(name="User", value=str(interaction.user.id), inline=True)
        embed.add_field(name="Guild", value=guild, inline=True)
        embed.add_field(name="Exception", value=type(error).__name__, inline=True)
        embed.add_field(
            name="Location", value=_last_frame_location(error), inline=False
        )
        if suppressed:
            embed.add_field(name="Suppressed", value=str(suppressed), inline=True)
        return embed

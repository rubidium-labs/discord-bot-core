"""The single handler for errors raised by commands, views and modals.

``CoreCommandTree.on_error`` (and the UI kit's ``BaseView``/``BaseModal``) delegate
here. The handler classifies the error, replies ephemerally, logs it and — for
unexpected errors only — optionally reports it to a log channel. It never raises.

The ephemeral reply goes to the invoking user, so it is translated per that user's
locale (falling back to ``en-US``). The error-log channel embed is for the team and
stays in English on purpose, to avoid noise from mixed locales.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import discord
from discord import app_commands

from discord_bot_core.errors.exceptions import OwnerOnlyError, UserFacingError
from discord_bot_core.i18n import translate
from discord_bot_core.settings import CoreSettings

logger = logging.getLogger(__name__)

_REPORT_WINDOW_SECONDS = 60.0


@dataclass(frozen=True)
class Outcome:
    """The result of classifying an error.

    Attributes:
        message: The text shown to the user: either a symbolic catalog key (the
            core's own messages, translated per the user's locale) or, for a
            :class:`UserFacingError` without a ``message_key``, the application's own
            text (passed through).
        level: The log level for the error.
        expected: ``True`` for errors the handler understands (no traceback, no
            report); ``False`` for the unexpected path.
        format_args: Values for the ``{placeholder}`` fields of a catalog key.
    """

    message: str
    level: int
    expected: bool
    format_args: dict[str, Any] = field(default_factory=dict)
    translatable: bool = True


def _permissions_names(names: list[str]) -> str:
    readable = [
        name.replace("_", " ").replace("guild", "server").title() for name in names
    ]
    if len(readable) == 1:
        return readable[0]
    return ", ".join(readable[:-1]) + " and " + readable[-1]


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
        await self._reply(
            interaction,
            await self._localized(interaction, outcome),
        )

    async def _localized(
        self,
        interaction: discord.Interaction,
        outcome: Outcome,
    ) -> str:
        r"""Translate the outcome's message when it is a core key, else pass it through.

        A ``UserFacingError`` without a ``message_key`` carries application text
        already (``translatable`` is ``False``) and is passed through; the core's own
        messages and ``UserFacingError``\\ s with a ``message_key`` are translated per
        the invoking user's locale.
        """
        if not outcome.translatable:
            return outcome.message
        return await translate(interaction, outcome.message, **outcome.format_args)

    def classify(self, error: BaseException, error_id: str | None = None) -> Outcome:
        """Map an unwrapped exception to the message, log level and path.

        The ``message`` of the returned outcome is a catalog key for the core's own
        messages (translated per the user's locale when replying) or, for a
        :class:`UserFacingError` without a ``message_key``, the application's own text.

        Args:
            error: The original exception (not a ``CommandInvokeError``).
            error_id: The id to embed in the generic message; generated when omitted.

        Returns:
            The outcome for this error.
        """
        if isinstance(error, UserFacingError):
            if error.message_key is None:
                return Outcome(
                    error.message, logging.INFO, expected=True, translatable=False
                )
            return Outcome(
                error.message_key,
                logging.INFO,
                expected=True,
                format_args=dict(error.format_args),
            )
        if isinstance(error, OwnerOnlyError):
            return Outcome("errors.check_failure", logging.INFO, expected=True)
        if isinstance(error, app_commands.NoPrivateMessage):
            return Outcome("errors.no_private_message", logging.INFO, expected=True)
        if isinstance(
            error, (app_commands.MissingPermissions, app_commands.BotMissingPermissions)
        ):
            return Outcome(
                "errors.permissions",
                logging.INFO,
                expected=True,
                format_args={
                    "permissions": _permissions_names(error.missing_permissions)
                },
            )
        if isinstance(error, app_commands.CommandOnCooldown):
            return Outcome(
                "errors.cooldown",
                logging.INFO,
                expected=True,
                format_args={"seconds": round(error.retry_after)},
            )
        if isinstance(
            error, (app_commands.CommandNotFound, app_commands.CommandSignatureMismatch)
        ):
            return Outcome("errors.out_of_date", logging.WARNING, expected=True)
        if isinstance(error, app_commands.TransformerError):
            return Outcome(
                "errors.transformer",
                logging.INFO,
                expected=True,
                format_args={"option": error.transformer._error_display_name},
            )
        if isinstance(error, app_commands.CheckFailure):
            return Outcome("errors.check_failure", logging.INFO, expected=True)
        if error_id is None:
            error_id = secrets.token_hex(4)
        return Outcome(
            "errors.generic",
            logging.ERROR,
            False,
            format_args={"error_id": error_id},
        )

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

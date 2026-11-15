"""Core settings, validated at start and never logged in full."""

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRETS_DIR = Path("/run/secrets")
"""Where Docker and Compose mount secrets, one file per secret."""


class Environment(StrEnum):
    """The deployment environment, which selects dev-only command behaviour."""

    DEV = "dev"
    PROD = "prod"


class CoreSettings(BaseSettings):
    """The settings every bot needs, loaded from the environment or secret files.

    Names map to environment variables case-insensitively (`discord_token` is
    `DISCORD_TOKEN`) and, for secrets, to a file of the same name in the secrets
    directory. Priority, highest first: constructor arguments, environment
    variables, the `.env` file, the secrets directory.

    Use :meth:`load` at start; construct the model directly in tests. Secret
    fields are :class:`~pydantic.SecretStr`, so ``repr``, ``str`` and
    ``model_dump`` mask them.

    Example:
        >>> settings = CoreSettings(discord_token="x", dev_guild_id=1)
        >>> settings.environment.value
        'prod'
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    discord_token: SecretStr
    dev_guild_id: PositiveInt
    environment: Environment = Environment.PROD
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    error_log_channel_id: PositiveInt | None = None
    database_url: SecretStr | None = None

    @classmethod
    def load(cls, secrets_dir: Path | str = DEFAULT_SECRETS_DIR) -> CoreSettings:
        """Load the settings, reading secrets from ``secrets_dir`` if it exists.

        The directory is only passed on when it exists, because
        pydantic-settings warns about a missing one; a laptop without
        ``/run/secrets`` therefore loads without noise.

        Args:
            secrets_dir: Directory holding one file per secret, named after the
                field. Defaults to :data:`DEFAULT_SECRETS_DIR`.

        Returns:
            The validated settings.

        Raises:
            pydantic.ValidationError: A required field is missing or invalid.
                The error names the field, never its value.

        Example:
            >>> settings = CoreSettings.load(Path("/run/secrets"))  # doctest: +SKIP
        """
        directory = Path(secrets_dir)
        if directory.is_dir():
            return cls(_secrets_dir=directory)  # type: ignore[call-arg]
        return cls()  # type: ignore[call-arg]

    def describe(self) -> dict[str, str]:
        """Return the non-secret fields, safe to log at start.

        The token and the database URL never appear; the database is reduced to
        ``configured`` or ``not configured``.

        Returns:
            A mapping of field names to string values, plus ``database``.
        """
        return {
            "environment": self.environment.value,
            "log_level": self.log_level,
            "dev_guild_id": str(self.dev_guild_id),
            "error_log_channel_id": (
                str(self.error_log_channel_id)
                if self.error_log_channel_id is not None
                else "not configured"
            ),
            "database": (
                "configured" if self.database_url is not None else "not configured"
            ),
        }

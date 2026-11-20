"""Tests for CoreSettings: validation, sources, masking and describe()."""

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from discord_bot_core.settings import (
    DEFAULT_SECRETS_DIR,
    CoreSettings,
    Environment,
    load,
)

TOKEN = "super-secret-token"
DATABASE_URL = "postgresql+asyncpg://user:hunter2@localhost/db"


def make_settings(**overrides: object) -> CoreSettings:
    values: dict[str, object] = {"discord_token": TOKEN, "dev_guild_id": 42}
    values.update(overrides)
    return CoreSettings(_env_file=None, **values)


def test_required_fields_fail_naming_the_field_not_the_value() -> None:
    with pytest.raises(ValidationError) as excinfo:
        CoreSettings(_env_file=None)

    errors = excinfo.value.errors()
    missing = {error["loc"] for error in errors if error["type"] == "missing"}
    assert missing == {("discord_token",), ("dev_guild_id",)}
    assert TOKEN not in str(excinfo.value)


def test_dev_guild_id_must_be_positive() -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(dev_guild_id=0)
    assert excinfo.value.errors()[0]["loc"] == ("dev_guild_id",)


def test_environment_defaults_to_prod() -> None:
    assert make_settings().environment is Environment.PROD


def test_optional_fields_default() -> None:
    settings = make_settings()
    assert settings.log_level == "INFO"
    assert settings.error_log_channel_id is None
    assert settings.database_url is None


def test_environment_enum_values() -> None:
    assert Environment.DEV == "dev"
    assert Environment.PROD == "prod"


def test_default_secrets_dir() -> None:
    assert DEFAULT_SECRETS_DIR == Path("/run/secrets")


def test_load_reads_secrets_dir(tmp_path: Path) -> None:
    (tmp_path / "discord_token").write_text(TOKEN)
    (tmp_path / "dev_guild_id").write_text("7")

    settings = CoreSettings.load(secrets_dir=tmp_path)

    assert settings.discord_token.get_secret_value() == TOKEN
    assert settings.dev_guild_id == 7


def test_load_accepts_str_path(tmp_path: Path) -> None:
    (tmp_path / "discord_token").write_text(TOKEN)
    (tmp_path / "dev_guild_id").write_text("7")

    settings = CoreSettings.load(secrets_dir=str(tmp_path))

    assert settings.dev_guild_id == 7


def test_environment_overrides_secrets_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "discord_token").write_text("from-file")
    (tmp_path / "dev_guild_id").write_text("1")
    monkeypatch.setenv("DISCORD_TOKEN", "from-env")
    monkeypatch.setenv("DEV_GUILD_ID", "2")

    settings = CoreSettings.load(secrets_dir=tmp_path)

    assert settings.discord_token.get_secret_value() == "from-env"
    assert settings.dev_guild_id == 2


def test_secrets_file_used_when_no_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("DEV_GUILD_ID", raising=False)
    (tmp_path / "discord_token").write_text("from-file")
    (tmp_path / "dev_guild_id").write_text("3")

    settings = CoreSettings.load(secrets_dir=tmp_path)

    assert settings.discord_token.get_secret_value() == "from-file"
    assert settings.dev_guild_id == 3


def test_trailing_newline_in_secret_file_is_stripped(tmp_path: Path) -> None:
    (tmp_path / "discord_token").write_text(TOKEN + "\n")
    (tmp_path / "dev_guild_id").write_text("9")

    settings = CoreSettings.load(secrets_dir=tmp_path)

    assert settings.discord_token.get_secret_value() == TOKEN


def test_missing_secrets_dir_does_not_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", TOKEN)
    monkeypatch.setenv("DEV_GUILD_ID", "5")

    settings = CoreSettings.load(secrets_dir=tmp_path / "does-not-exist")

    assert settings.dev_guild_id == 5
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_load_without_secrets_dir_does_not_warn(
    monkeypatch: pytest.MonkeyPatch, recwarn: pytest.WarningsRecorder
) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", TOKEN)
    monkeypatch.setenv("DEV_GUILD_ID", "5")

    CoreSettings.load(secrets_dir="/nonexistent/secrets/dir")

    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]


def test_unknown_environment_variables_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNRELATED_VARIABLE", "whatever")
    monkeypatch.setenv("DISCORD_TOKEN", TOKEN)
    monkeypatch.setenv("DEV_GUILD_ID", "11")

    settings = load()

    assert settings.dev_guild_id == 11
    assert not hasattr(settings, "unrelated_variable")


def test_dotenv_file_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.delenv("DEV_GUILD_ID", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(f"DISCORD_TOKEN={TOKEN}\nDEV_GUILD_ID=13\n")

    settings = CoreSettings(_env_file=env_file)

    assert settings.discord_token.get_secret_value() == TOKEN
    assert settings.dev_guild_id == 13


def test_environment_overrides_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"DISCORD_TOKEN={TOKEN}\nDEV_GUILD_ID=13\n")
    monkeypatch.setenv("DEV_GUILD_ID", "14")

    settings = CoreSettings(_env_file=env_file)

    assert settings.dev_guild_id == 14


def test_init_arguments_override_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEV_GUILD_ID", "15")

    settings = make_settings(dev_guild_id=16)

    assert settings.dev_guild_id == 16


def test_settings_are_frozen() -> None:
    settings = make_settings()

    with pytest.raises(ValidationError):
        settings.dev_guild_id = 1  # type: ignore[misc]


def test_repr_and_str_never_contain_secrets() -> None:
    settings = make_settings(database_url=DATABASE_URL)

    for text in (repr(settings), str(settings)):
        assert TOKEN not in text
        assert DATABASE_URL not in text
        assert "hunter2" not in text


def test_model_dump_never_contains_secrets() -> None:
    settings = make_settings(database_url=DATABASE_URL)

    dumped = settings.model_dump()
    text = str(dumped)

    assert TOKEN not in text
    assert DATABASE_URL not in text
    assert "hunter2" not in text
    assert isinstance(dumped["discord_token"], SecretStr)
    assert isinstance(dumped["database_url"], SecretStr)


def test_database_url_masked_in_repr() -> None:
    settings = make_settings(database_url=DATABASE_URL)

    assert "database_url=SecretStr('**********')" in repr(settings)


def test_describe_without_database() -> None:
    settings = make_settings()

    assert settings.describe() == {
        "environment": "prod",
        "log_level": "INFO",
        "dev_guild_id": "42",
        "error_log_channel_id": "not configured",
        "database": "not configured",
    }


def test_describe_with_database_and_error_channel() -> None:
    settings = make_settings(
        environment=Environment.DEV,
        log_level="DEBUG",
        error_log_channel_id=99,
        database_url=DATABASE_URL,
    )

    described = settings.describe()

    assert described == {
        "environment": "dev",
        "log_level": "DEBUG",
        "dev_guild_id": "42",
        "error_log_channel_id": "99",
        "database": "configured",
    }
    assert DATABASE_URL not in str(described)
    assert "hunter2" not in str(described)


def test_default_locale_defaults_to_en_us() -> None:
    assert make_settings().default_locale == "en-US"


def test_default_locale_accepts_a_supported_locale() -> None:
    assert make_settings(default_locale="fr").default_locale == "fr"


def test_default_locale_rejects_an_invalid_value() -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_settings(default_locale="xx-YY")
    assert excinfo.value.errors()[0]["loc"] == ("default_locale",)

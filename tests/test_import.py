"""Tests for importing the package: it must have no side effects."""

import subprocess
import sys

import discord_bot_core


def test_version_is_a_string() -> None:
    assert isinstance(discord_bot_core.__version__, str)
    assert discord_bot_core.__version__


def test_import_has_no_side_effects() -> None:
    """Importing the package creates no settings, bot or database engine."""
    code = (
        "import sys\n"
        "import discord_bot_core\n"
        "modules = sys.modules\n"
        "for name in ('discord', 'sqlalchemy', 'pydantic_settings'):\n"
        "    assert name not in modules, name\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

"""Tests for extension discovery."""

from discord_bot_core.extensions import discover_extensions

PACKAGE = "tests.extensions.fixture_pkg"


def test_skips_private_modules() -> None:
    names = discover_extensions(PACKAGE)
    assert f"{PACKAGE}._private" not in names


def test_includes_modules_and_subpackages() -> None:
    names = discover_extensions(PACKAGE)
    assert f"{PACKAGE}.good" in names
    assert f"{PACKAGE}.failing" in names
    assert f"{PACKAGE}.subpkg" in names


def test_returns_sorted_full_names() -> None:
    names = discover_extensions(PACKAGE)
    assert names == sorted(names)
    assert all(name.startswith(f"{PACKAGE}.") for name in names)

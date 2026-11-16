"""Fixtures for the bot tests.

The extension fixture package is imported by its absolute name
(``tests.extensions.fixture_pkg``), so the repository root must be importable.
pytest does not add it to ``sys.path`` by default, hence the ``syspath_prepend``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _importable_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``tests.extensions.fixture_pkg`` importable by its absolute name."""
    monkeypatch.syspath_prepend(str(REPO_ROOT))

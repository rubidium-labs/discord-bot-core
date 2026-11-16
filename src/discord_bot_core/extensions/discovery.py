"""Discovery of the extensions inside a package.

Pure and testable: it imports the package (not its modules) and lists the modules
and sub-packages it contains. Whether a module actually defines ``setup`` is checked
lazily by ``load``, so discovery never executes extension code.
"""

from __future__ import annotations

import importlib
import pkgutil

__all__ = ["discover_extensions"]


def discover_extensions(package: str) -> list[str]:
    """List the extensions inside ``package``.

    Imports ``package`` and iterates its modules with :func:`pkgutil.iter_modules`.
    Names starting with ``_`` are skipped; sub-packages are included as candidates
    (their ``setup`` is checked when they are loaded). Only the package itself is
    imported, never its modules.

    Args:
        package: The importable package that holds the extensions (for example
            ``rubidium_bot.cogs``).

    Returns:
        The sorted, fully-qualified names of the candidate extensions (for example
        ``rubidium_bot.cogs.secret_santa``).
    """
    module = importlib.import_module(package)
    names = [
        f"{package}.{info.name}"
        for info in pkgutil.iter_modules(module.__path__)
        if not info.name.startswith("_")
    ]
    return sorted(names)

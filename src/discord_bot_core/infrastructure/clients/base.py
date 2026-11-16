"""The base every outside HTTP client inherits from.

One small base, so every future client does not repeat the same
session/timeout/error code. It performs no retry, backoff or caching: there is no
first user to tell what is needed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp

from discord_bot_core.errors import ExternalServiceError


class BaseHttpClient:
    """A JSON-over-HTTP client with a lazily created session.

    The :class:`aiohttp.ClientSession` is created inside the running loop on the
    first request, not in ``__init__`` (a session binds to the loop that creates
    it). An injected session is used as-is and is never closed by :meth:`aclose`.

    Attributes:
        _base_url: The base URL, without a trailing slash.
        _session: The session, or ``None`` until the first request.
        _owns_session: Whether :meth:`aclose` should close the session.
        _timeout: Total timeout in seconds for a request.
        _headers: Headers sent with every request; never logged.
    """

    def __init__(
        self,
        base_url: str,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: float = 10.0,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Store the configuration; do not create a session.

        Args:
            base_url: The base URL; a trailing ``/`` is stripped.
            session: An existing session to use as-is, or ``None`` to create one.
            timeout: Total timeout in seconds for each request.
            headers: Headers sent with every request (for example a token).
        """
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._owns_session = session is None
        self._timeout = timeout
        self._headers = dict(headers) if headers is not None else {}

    @property
    def _get_session(self) -> aiohttp.ClientSession:
        """Return the session, creating it on first use inside the running loop."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                headers=self._headers,
            )
        return self._session

    async def request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform a request and return the decoded JSON body.

        Args:
            method: The HTTP method (``GET``, ``POST``, ...).
            path: The request path, relative to the base URL.
            **kwargs: Passed to :meth:`aiohttp.ClientSession.request`.

        Returns:
            The decoded JSON body.

        Raises:
            ExternalServiceError: On a non-2xx response, a transport error, a
                timeout or an invalid JSON body. The message is sanitised: it
                carries the method and path only, never the query string or the
                headers.
        """
        session = self._get_session
        safe_path = path.split("?", 1)[0]
        try:
            async with session.request(method, path, **kwargs) as response:
                if not 200 <= response.status < 300:
                    raise ExternalServiceError(
                        f"{method} {safe_path} failed with status {response.status}",
                        status=response.status,
                    )
                return await response.json(content_type=None)
        except ExternalServiceError:
            raise
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise ExternalServiceError(
                f"{method} {safe_path} failed: {type(exc).__name__}"
            ) from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExternalServiceError(
                f"{method} {safe_path} returned invalid JSON"
            ) from exc

    async def aclose(self) -> None:
        """Close the session, but only if this client created it."""
        if self._session is not None and self._owns_session:
            await self._session.close()
        self._session = None

"""Tests for BaseHttpClient, using a fake session to avoid the network."""

from __future__ import annotations

from typing import Any

import aiohttp
import pytest

from discord_bot_core.errors import ExternalServiceError
from discord_bot_core.infrastructure.clients import BaseHttpClient


class FakeResponse:
    def __init__(
        self, status: int, payload: Any = None, *, error: Exception | None = None
    ) -> None:
        self.status = status
        self._payload = payload
        self._error = error

    async def json(self, *, content_type: str | None = "application/json") -> Any:
        if self._error is not None:
            raise self._error
        return self._payload

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class FakeSession:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self._response = response
        self.requests: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    def request(self, method: str, path: str, **kwargs: Any) -> FakeResponse:
        self.requests.append((method, path, kwargs))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def close(self) -> None:
        self.closed = True


def test_base_url_trailing_slash_stripped() -> None:
    client = BaseHttpClient(
        "https://api.example.com/v1/", session=FakeSession(FakeResponse(200))
    )
    assert client._base_url == "https://api.example.com/v1"


def test_session_is_lazy() -> None:
    client = BaseHttpClient("https://api.example.com")
    assert client._session is None


async def test_request_json_returns_body() -> None:
    session = FakeSession(FakeResponse(200, {"ok": True}))
    client = BaseHttpClient("https://api.example.com", session=session)

    result = await client.request_json("GET", "/widgets")

    assert result == {"ok": True}
    assert session.requests == [("GET", "/widgets", {})]


async def test_non_2xx_raises_sanitised_error() -> None:
    session = FakeSession(FakeResponse(404))
    client = BaseHttpClient("https://api.example.com", session=session)

    with pytest.raises(ExternalServiceError) as excinfo:
        await client.request_json("GET", "/widgets?secret=1")

    assert excinfo.value.status == 404
    assert "404" in str(excinfo.value)
    assert "secret" not in str(excinfo.value)


async def test_transport_error_raises() -> None:
    session = FakeSession(aiohttp.ClientConnectionError("boom"))
    client = BaseHttpClient("https://api.example.com", session=session)

    with pytest.raises(ExternalServiceError):
        await client.request_json("GET", "/widgets")


async def test_timeout_raises() -> None:
    session = FakeSession(TimeoutError())
    client = BaseHttpClient("https://api.example.com", session=session)

    with pytest.raises(ExternalServiceError):
        await client.request_json("GET", "/widgets")


async def test_invalid_json_raises() -> None:
    session = FakeSession(FakeResponse(200, error=ValueError("bad json")))
    client = BaseHttpClient("https://api.example.com", session=session)

    with pytest.raises(ExternalServiceError):
        await client.request_json("GET", "/widgets")


async def test_aclose_closes_own_session() -> None:
    client = BaseHttpClient("https://api.example.com")
    session = FakeSession(FakeResponse(200, {}))
    client._session = session
    client._owns_session = True

    await client.aclose()

    assert session.closed
    assert client._session is None


async def test_aclose_leaves_injected_session_open() -> None:
    session = FakeSession(FakeResponse(200, {}))
    client = BaseHttpClient("https://api.example.com", session=session)

    await client.aclose()

    assert not session.closed


async def test_creates_session_with_timeout_and_headers() -> None:
    client = BaseHttpClient(
        "https://api.example.com",
        timeout=5.0,
        headers={"Authorization": "Bearer token"},
    )

    session = client._get_session

    try:
        assert isinstance(session, aiohttp.ClientSession)
        assert session.timeout.total == 5.0
        assert session.headers["Authorization"] == "Bearer token"
    finally:
        await client.aclose()

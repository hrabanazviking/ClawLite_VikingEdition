from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx

from clawlite.channels.discord import DiscordChannel


def _response(*, status: int, url: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    request = httpx.Request("POST", url)
    if payload is None:
        return httpx.Response(status, request=request)
    return httpx.Response(status, json=payload, request=request)


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    async def post(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        self.posts.append((url, dict(json or {})))
        if not self._responses:
            raise AssertionError("unexpected discord post")
        return self._responses.pop(0)

    async def aclose(self) -> None:
        self.closed = True


def test_discord_channel_reuses_persistent_client_across_sends(monkeypatch) -> None:
    async def _scenario() -> None:
        client = _FakeClient(
            [
                _response(status=200, url="https://discord.com/api/v10/channels/123/messages", payload={"id": "m1"}),
                _response(status=200, url="https://discord.com/api/v10/channels/123/messages", payload={"id": "m2"}),
            ]
        )
        created: list[_FakeClient] = []

        def _factory(*args, **kwargs):
            del args, kwargs
            created.append(client)
            return client

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

        channel = DiscordChannel(config={"token": "bot-token"})
        await channel.start()

        first = await channel.send(target="123", text="hello")
        second = await channel.send(target="123", text="again")

        await channel.stop()

        assert first == "discord:sent:m1"
        assert second == "discord:sent:m2"
        assert len(created) == 1
        assert len(client.posts) == 2
        assert client.closed is True

    asyncio.run(_scenario())


def test_discord_send_retries_429_using_retry_after(monkeypatch) -> None:
    async def _scenario() -> None:
        first = _response(
            status=429,
            url="https://discord.com/api/v10/channels/123/messages",
            payload={"retry_after": 1.25},
        )
        second = _response(
            status=200,
            url="https://discord.com/api/v10/channels/123/messages",
            payload={"id": "ok-1"},
        )
        client = _FakeClient([first, second])

        def _factory(*args, **kwargs):
            del args, kwargs
            return client

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

        channel = DiscordChannel(config={"token": "bot-token", "send_retry_attempts": 2})
        await channel.start()

        sleep_mock = AsyncMock()
        with patch("clawlite.channels.discord.asyncio.sleep", new=sleep_mock):
            out = await channel.send(target="123", text="hello")

        await channel.stop()

        assert out == "discord:sent:ok-1"
        assert len(client.posts) == 2
        assert sleep_mock.await_count == 1
        assert sleep_mock.await_args.args == (1.25,)

    asyncio.run(_scenario())

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx

from clawlite.channels.slack import SlackChannel


def _response(
    *,
    status: int,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", url)
    if payload is None:
        return httpx.Response(status, request=request, headers=headers)
    return httpx.Response(status, json=payload, request=request, headers=headers)


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = list(responses)
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    async def post(self, url: str, json: dict[str, Any] | None = None) -> httpx.Response:
        self.posts.append((url, dict(json or {})))
        if not self._responses:
            raise AssertionError("unexpected slack post")
        return self._responses.pop(0)

    async def aclose(self) -> None:
        self.closed = True


def test_slack_channel_reuses_persistent_client_across_sends(monkeypatch) -> None:
    async def _scenario() -> None:
        client = _FakeClient(
            [
                _response(status=200, url="https://slack.com/api/chat.postMessage", payload={"ok": True, "ts": "1.1"}),
                _response(status=200, url="https://slack.com/api/chat.postMessage", payload={"ok": True, "ts": "1.2"}),
            ]
        )
        created: list[_FakeClient] = []

        def _factory(*args, **kwargs):
            del args, kwargs
            created.append(client)
            return client

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

        channel = SlackChannel(config={"bot_token": "xoxb-1"})
        await channel.start()

        first = await channel.send(target="C123", text="hello")
        second = await channel.send(target="C123", text="again")

        await channel.stop()

        assert first == "slack:sent:C123:1.1"
        assert second == "slack:sent:C123:1.2"
        assert len(created) == 1
        assert len(client.posts) == 2
        assert client.closed is True

    asyncio.run(_scenario())


def test_slack_send_retries_http_429_with_retry_after(monkeypatch) -> None:
    async def _scenario() -> None:
        first = _response(
            status=429,
            url="https://slack.com/api/chat.postMessage",
            payload={"ok": False, "error": "ratelimited"},
            headers={"Retry-After": "2.0"},
        )
        second = _response(
            status=200,
            url="https://slack.com/api/chat.postMessage",
            payload={"ok": True, "ts": "1700.1"},
        )
        client = _FakeClient([first, second])

        def _factory(*args, **kwargs):
            del args, kwargs
            return client

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

        channel = SlackChannel(config={"bot_token": "xoxb-1", "send_retry_attempts": 2})
        await channel.start()

        sleep_mock = AsyncMock()
        with patch("clawlite.channels.slack.asyncio.sleep", new=sleep_mock):
            out = await channel.send(target="C123", text="hello")

        await channel.stop()

        assert out == "slack:sent:C123:1700.1"
        assert len(client.posts) == 2
        assert sleep_mock.await_count == 1
        assert sleep_mock.await_args.args == (2.0,)

    asyncio.run(_scenario())


def test_slack_send_retries_api_ratelimited_error(monkeypatch) -> None:
    async def _scenario() -> None:
        first = _response(
            status=200,
            url="https://slack.com/api/chat.postMessage",
            payload={"ok": False, "error": "ratelimited", "retry_after": 1.5},
        )
        second = _response(
            status=200,
            url="https://slack.com/api/chat.postMessage",
            payload={"ok": True, "ts": "1700.2"},
        )
        client = _FakeClient([first, second])

        def _factory(*args, **kwargs):
            del args, kwargs
            return client

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

        channel = SlackChannel(config={"bot_token": "xoxb-1", "send_retry_attempts": 2})
        await channel.start()

        sleep_mock = AsyncMock()
        with patch("clawlite.channels.slack.asyncio.sleep", new=sleep_mock):
            out = await channel.send(target="C123", text="hello")

        await channel.stop()

        assert out == "slack:sent:C123:1700.2"
        assert len(client.posts) == 2
        assert sleep_mock.await_count == 1
        assert sleep_mock.await_args.args == (1.5,)

    asyncio.run(_scenario())

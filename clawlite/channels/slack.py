from __future__ import annotations

import asyncio
from typing import Any

import httpx

from clawlite.channels.base import BaseChannel


class SlackChannel(BaseChannel):
    def __init__(self, *, config: dict[str, Any], on_message=None) -> None:
        super().__init__(name="slack", config=config, on_message=on_message)
        bot_token = str(config.get("bot_token", config.get("botToken", "")) or "").strip()
        if not bot_token:
            raise ValueError("slack bot_token is required")
        self.bot_token = bot_token
        self.app_token = str(config.get("app_token", config.get("appToken", "")) or "").strip()
        self.api_base = str(config.get("api_base", config.get("apiBase", "https://slack.com/api")) or "https://slack.com/api").strip().rstrip("/")
        self.timeout_s = max(0.1, float(config.get("timeout_s", config.get("timeoutS", 10.0)) or 10.0))
        self.send_retry_attempts = max(1, int(config.get("send_retry_attempts", config.get("sendRetryAttempts", 3)) or 3))
        self.send_retry_after_default_s = max(
            0.0,
            float(config.get("send_retry_after_default_s", config.get("sendRetryAfterDefaultS", 1.0)) or 1.0),
        )
        self._headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        self._client: httpx.AsyncClient | None = None

    @staticmethod
    def _parse_retry_after(raw: str) -> float | None:
        value = str(raw or "").strip()
        if not value:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if parsed < 0.0:
            return 0.0
        return parsed

    def _extract_retry_after(self, *, response: httpx.Response, payload: dict[str, Any] | None = None) -> float:
        header_retry_after = self._parse_retry_after(response.headers.get("Retry-After", ""))
        if header_retry_after is not None:
            return header_retry_after
        if isinstance(payload, dict):
            body_retry_after = self._parse_retry_after(str(payload.get("retry_after", "")))
            if body_retry_after is not None:
                return body_retry_after
        return self.send_retry_after_default_s

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_s, headers=self._headers)
        self._running = True

    async def stop(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            close_fn = getattr(client, "aclose", None)
            if callable(close_fn):
                await close_fn()
        self._running = False

    async def send(self, *, target: str, text: str, metadata: dict[str, Any] | None = None) -> str:
        if not self._running:
            raise RuntimeError("slack_not_running")

        channel = str(target or "").strip()
        if not channel:
            raise ValueError("slack target(channel) is required")

        url = f"{self.api_base}/chat.postMessage"
        payload = {
            "channel": channel,
            "text": str(text or ""),
        }
        client = self._client
        if client is None:
            raise RuntimeError("slack_not_running")

        for attempt in range(1, self.send_retry_attempts + 1):
            try:
                response = await client.post(url, json=payload)
            except httpx.HTTPError as exc:
                self._last_error = str(exc)
                raise RuntimeError("slack_send_request_error") from exc

            data: dict[str, Any] | None = None
            if response.content:
                try:
                    parsed = response.json()
                except Exception:
                    parsed = None
                if isinstance(parsed, dict):
                    data = parsed

            if response.status_code == 429:
                self._last_error = "http:429"
                if attempt >= self.send_retry_attempts:
                    raise RuntimeError("slack_send_rate_limited")
                await asyncio.sleep(self._extract_retry_after(response=response, payload=data))
                continue

            if response.status_code < 200 or response.status_code >= 300:
                self._last_error = f"http:{response.status_code}"
                raise RuntimeError(f"slack_send_http_{response.status_code}")

            if data is None:
                self._last_error = "invalid_json"
                raise RuntimeError("slack_send_invalid_json")

            if not bool(data.get("ok", False)):
                code = str(data.get("error", "unknown") or "unknown").strip() or "unknown"
                self._last_error = code
                is_rate_limited = code in {"ratelimited", "rate_limited"}
                if is_rate_limited and attempt < self.send_retry_attempts:
                    await asyncio.sleep(self._extract_retry_after(response=response, payload=data))
                    continue
                raise RuntimeError(f"slack_send_api_error:{code}")

            ts = str(data.get("ts", "") or "").strip()
            if not ts:
                self._last_error = "missing_ts"
                raise RuntimeError("slack_send_missing_ts")
            self._last_error = ""
            return f"slack:sent:{channel}:{ts}"

        raise RuntimeError("slack_send_rate_limited")

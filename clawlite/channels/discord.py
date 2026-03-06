from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import httpx

from clawlite.channels.base import BaseChannel


class DiscordChannel(BaseChannel):
    def __init__(self, *, config: dict[str, Any], on_message=None) -> None:
        super().__init__(name="discord", config=config, on_message=on_message)
        token = str(config.get("token", "") or "").strip()
        if not token:
            raise ValueError("discord token is required")
        self.token = token
        self.api_base = str(config.get("api_base", config.get("apiBase", "https://discord.com/api/v10")) or "https://discord.com/api/v10").strip().rstrip("/")
        self.timeout_s = max(0.1, float(config.get("timeout_s", config.get("timeoutS", 10.0)) or 10.0))
        self.send_retry_attempts = max(1, int(config.get("send_retry_attempts", config.get("sendRetryAttempts", 3)) or 3))
        self.send_retry_after_default_s = max(
            0.0,
            float(config.get("send_retry_after_default_s", config.get("sendRetryAfterDefaultS", 1.0)) or 1.0),
        )
        self._headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
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

    def _extract_retry_after(self, response: httpx.Response) -> float:
        header_retry_after = self._parse_retry_after(response.headers.get("Retry-After", ""))
        if header_retry_after is not None:
            return header_retry_after
        reset_after = self._parse_retry_after(response.headers.get("X-RateLimit-Reset-After", ""))
        if reset_after is not None:
            return reset_after
        if response.content:
            try:
                data = response.json()
            except Exception:
                data = {}
            if isinstance(data, dict):
                body_retry_after = self._parse_retry_after(str(data.get("retry_after", "")))
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
            raise RuntimeError("discord_not_running")

        channel_id = str(target or "").strip()
        if not channel_id:
            raise ValueError("discord target(channel_id) is required")

        payload = {"content": str(text or "")}
        url = f"{self.api_base}/channels/{channel_id}/messages"
        client = self._client
        if client is None:
            raise RuntimeError("discord_not_running")

        for attempt in range(1, self.send_retry_attempts + 1):
            try:
                response = await client.post(url, json=payload)
            except httpx.HTTPError as exc:
                self._last_error = str(exc)
                raise RuntimeError("discord_send_request_error") from exc

            if response.status_code == 429:
                self._last_error = "http:429"
                if attempt >= self.send_retry_attempts:
                    raise RuntimeError("discord_send_rate_limited")
                retry_after = self._extract_retry_after(response)
                await asyncio.sleep(retry_after)
                continue

            if response.status_code < 200 or response.status_code >= 300:
                self._last_error = f"http:{response.status_code}"
                raise RuntimeError(f"discord_send_http_{response.status_code}")

            if response.content:
                try:
                    data = response.json()
                except Exception:
                    data = {}
            else:
                data = {}
            message_id = str(data.get("id", "") or "").strip()
            if not message_id:
                digest = hashlib.sha256(f"{channel_id}:{text}".encode("utf-8")).hexdigest()[:16]
                message_id = f"fallback-{digest}"
            self._last_error = ""
            return f"discord:sent:{message_id}"

        raise RuntimeError("discord_send_rate_limited")

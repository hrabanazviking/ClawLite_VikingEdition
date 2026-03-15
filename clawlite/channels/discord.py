from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
import websockets

from clawlite.channels.base import BaseChannel, cancel_task

DISCORD_DEFAULT_API_BASE = "https://discord.com/api/v10"
DISCORD_DEFAULT_GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"
# 37377 base (GUILDS|GUILD_MESSAGES|DIRECT_MESSAGES|MESSAGE_CONTENT)
# + 1024  GUILD_MESSAGE_REACTIONS
# + 8192  DIRECT_MESSAGE_REACTIONS
DISCORD_DEFAULT_GATEWAY_INTENTS = 46593
DISCORD_TYPING_INTERVAL_S = 8.0
DISCORD_VOICE_MESSAGE_FLAG = 1 << 13  # 8192 — IS_VOICE_MESSAGE
DISCORD_VOICE_WAVEFORM_SAMPLES = 256


@dataclass(slots=True, frozen=True)
class _DiscordSendTarget:
    kind: str
    value: str


class DiscordChannel(BaseChannel):
    def __init__(self, *, config: dict[str, Any], on_message=None) -> None:
        super().__init__(name="discord", config=config, on_message=on_message)
        token = str(config.get("token", "") or "").strip()
        if not token:
            raise ValueError("discord token is required")
        self.token = token
        self.api_base = str(
            config.get("api_base", config.get("apiBase", DISCORD_DEFAULT_API_BASE))
            or DISCORD_DEFAULT_API_BASE
        ).strip().rstrip("/")
        self.gateway_url = str(
            config.get(
                "gateway_url",
                config.get("gatewayUrl", DISCORD_DEFAULT_GATEWAY_URL),
            )
            or DISCORD_DEFAULT_GATEWAY_URL
        ).strip()
        self.gateway_intents = max(
            0,
            int(
                config.get(
                    "gateway_intents",
                    config.get("gatewayIntents", DISCORD_DEFAULT_GATEWAY_INTENTS),
                )
                or DISCORD_DEFAULT_GATEWAY_INTENTS
            ),
        )
        self.timeout_s = max(
            0.1,
            float(config.get("timeout_s", config.get("timeoutS", 10.0)) or 10.0),
        )
        self.typing_enabled = bool(
            config.get("typing_enabled", config.get("typingEnabled", True))
        )
        self.typing_interval_s = max(
            0.5,
            float(
                config.get(
                    "typing_interval_s",
                    config.get("typingIntervalS", DISCORD_TYPING_INTERVAL_S),
                )
                or DISCORD_TYPING_INTERVAL_S
            ),
        )
        self.gateway_backoff_base_s = max(
            0.1,
            float(
                config.get(
                    "gateway_backoff_base_s",
                    config.get("gatewayBackoffBaseS", 2.0),
                )
                or 2.0
            ),
        )
        self.gateway_backoff_max_s = max(
            self.gateway_backoff_base_s,
            float(
                config.get(
                    "gateway_backoff_max_s",
                    config.get("gatewayBackoffMaxS", 30.0),
                )
                or 30.0
            ),
        )
        self.send_retry_attempts = max(
            1,
            int(
                config.get("send_retry_attempts", config.get("sendRetryAttempts", 3))
                or 3
            ),
        )
        self.send_retry_after_default_s = max(
            0.0,
            float(
                config.get(
                    "send_retry_after_default_s",
                    config.get("sendRetryAfterDefaultS", 1.0),
                )
                or 1.0
            ),
        )
        self.allow_from = self._normalize_allow_from(
            config.get("allow_from", config.get("allowFrom", []))
        )
        self._headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None
        self._ws: Any | None = None
        self._gateway_task: asyncio.Task[Any] | None = None
        self._heartbeat_task: asyncio.Task[Any] | None = None
        self._typing_tasks: dict[str, asyncio.Task[Any]] = {}
        self._dm_channel_ids: dict[str, str] = {}
        self._sequence: int | None = None
        self._session_id: str = ""
        self._resume_url: str = ""
        self._bot_user_id: str = ""
        self._application_id: str = ""

    @staticmethod
    def _normalize_allow_from(raw: Any) -> list[str]:
        if not isinstance(raw, list):
            return []
        values: list[str] = []
        for item in raw:
            value = str(item or "").strip()
            if value:
                values.append(value)
        return values

    def _is_allowed_sender(self, *, user_id: str, username: str = "") -> bool:
        if not self.allow_from:
            return True
        candidates = {str(user_id or "").strip()}
        normalized_username = str(username or "").strip().lstrip("@")
        if normalized_username:
            candidates.add(normalized_username)
            candidates.add(f"@{normalized_username}")
        allowed = {item.strip() for item in self.allow_from if str(item or "").strip()}
        return any(candidate in allowed for candidate in candidates)

    @staticmethod
    def _looks_like_snowflake(value: str) -> bool:
        raw = str(value or "").strip()
        return raw.isdigit() and len(raw) >= 5

    @classmethod
    def _parse_send_target(cls, raw: str) -> _DiscordSendTarget:
        target = str(raw or "").strip()
        if not target:
            return _DiscordSendTarget(kind="", value="")

        if target.startswith("<#") and target.endswith(">"):
            return _DiscordSendTarget(kind="channel", value=target[2:-1].strip())
        if target.startswith("<@") and target.endswith(">"):
            return _DiscordSendTarget(
                kind="user",
                value=target[2:-1].strip().lstrip("!"),
            )

        lowered = target.lower()
        if lowered.startswith("discord:"):
            target = target.split(":", 1)[1].strip()
            lowered = target.lower()

        for prefix, kind in (
            ("channel:", "channel"),
            ("group:", "channel"),
            ("user:", "user"),
            ("dm:", "user"),
            ("direct:", "user"),
        ):
            if lowered.startswith(prefix):
                value = target[len(prefix) :].strip()
                if kind == "channel" and ":thread:" in value:
                    _, _, thread_id = value.partition(":thread:")
                    thread = thread_id.strip()
                    if thread:
                        value = thread
                return _DiscordSendTarget(kind=kind, value=value)

        if ":thread:" in target:
            _, _, thread_id = target.partition(":thread:")
            thread = thread_id.strip()
            if thread:
                return _DiscordSendTarget(kind="channel", value=thread)

        return _DiscordSendTarget(kind="ambiguous", value=target)

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
        header_retry_after = self._parse_retry_after(
            response.headers.get("Retry-After", "")
        )
        if header_retry_after is not None:
            return header_retry_after
        reset_after = self._parse_retry_after(
            response.headers.get("X-RateLimit-Reset-After", "")
        )
        if reset_after is not None:
            return reset_after
        if response.content:
            try:
                data = response.json()
            except Exception:
                data = {}
            if isinstance(data, dict):
                body_retry_after = self._parse_retry_after(
                    str(data.get("retry_after", ""))
                )
                if body_retry_after is not None:
                    return body_retry_after
        return self.send_retry_after_default_s

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_s,
                headers=self._headers,
            )
        self._running = True
        if self.on_message is not None and (
            self._gateway_task is None or self._gateway_task.done()
        ):
            self._gateway_task = asyncio.create_task(self._gateway_runner())

    async def stop(self) -> None:
        self._running = False
        await cancel_task(self._gateway_task)
        self._gateway_task = None
        await cancel_task(self._heartbeat_task)
        self._heartbeat_task = None
        for task in list(self._typing_tasks.values()):
            await cancel_task(task)
        self._typing_tasks.clear()
        self._dm_channel_ids.clear()
        ws = self._ws
        self._ws = None
        if ws is not None:
            close_fn = getattr(ws, "close", None)
            if callable(close_fn):
                result = close_fn()
                if asyncio.iscoroutine(result):
                    await result
        client = self._client
        self._client = None
        if client is not None:
            close_fn = getattr(client, "aclose", None)
            if callable(close_fn):
                await close_fn()

    async def _post_json(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        error_prefix: str,
    ) -> httpx.Response:
        client = self._client
        if client is None:
            raise RuntimeError("discord_not_running")
        for attempt in range(1, self.send_retry_attempts + 1):
            try:
                response = await client.post(url, json=payload)
            except httpx.HTTPError as exc:
                self._last_error = str(exc)
                raise RuntimeError(f"{error_prefix}_request_error") from exc

            if response.status_code == 429:
                self._last_error = "http:429"
                if attempt >= self.send_retry_attempts:
                    raise RuntimeError(f"{error_prefix}_rate_limited")
                retry_after = self._extract_retry_after(response)
                await asyncio.sleep(retry_after)
                continue

            if response.status_code < 200 or response.status_code >= 300:
                self._last_error = f"http:{response.status_code}"
                raise RuntimeError(f"{error_prefix}_http_{response.status_code}")

            return response

        raise RuntimeError(f"{error_prefix}_rate_limited")

    async def _ensure_dm_channel_id(self, user_id: str) -> str:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise ValueError("discord user target is required")
        cached = self._dm_channel_ids.get(normalized_user_id, "")
        if cached:
            return cached
        response = await self._post_json(
            url=f"{self.api_base}/users/@me/channels",
            payload={"recipient_id": normalized_user_id},
            error_prefix="discord_dm_channel",
        )
        try:
            data = response.json() if response.content else {}
        except Exception:
            data = {}
        channel_id = str(data.get("id", "") or "").strip()
        if not channel_id:
            raise RuntimeError("discord_dm_channel_invalid_response")
        self._dm_channel_ids[normalized_user_id] = channel_id
        return channel_id

    async def send(
        self,
        *,
        target: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if not self._running:
            raise RuntimeError("discord_not_running")

        resolved_target = self._parse_send_target(target)
        if not resolved_target.value:
            raise ValueError("discord target(channel_id) is required")

        payload: dict[str, Any] = {"content": str(text or "")}
        metadata_payload = dict(metadata or {})
        reply_to_message_id = str(
            metadata_payload.get(
                "reply_to_message_id",
                metadata_payload.get("message_reference_id", ""),
            )
            or ""
        ).strip()
        if reply_to_message_id:
            payload["message_reference"] = {
                "message_id": reply_to_message_id,
                "fail_if_not_exists": False,
            }
            payload["allowed_mentions"] = {"replied_user": False}

        # Rich embeds — pass as metadata key "discord_embeds" or "embeds"
        raw_embeds = metadata_payload.get("discord_embeds") or metadata_payload.get("embeds")
        if isinstance(raw_embeds, list) and raw_embeds:
            payload["embeds"] = [
                e for e in raw_embeds if isinstance(e, dict)
            ][:10]  # Discord max 10 embeds per message

        # Message components (buttons, select menus) — pass as metadata key "discord_components"
        raw_components = metadata_payload.get("discord_components") or metadata_payload.get("components")
        if isinstance(raw_components, list) and raw_components:
            payload["components"] = [c for c in raw_components if isinstance(c, dict)][:5]  # Discord max 5 action rows

        # Poll — pass as metadata key "discord_poll": {"question": str, "answers": [str, ...], "duration_hours": int}
        raw_poll = metadata_payload.get("discord_poll")
        if isinstance(raw_poll, dict) and raw_poll.get("question") and raw_poll.get("answers"):
            answers_raw = [str(a) for a in raw_poll["answers"] if a][:10]
            payload["poll"] = {
                "question": {"text": str(raw_poll["question"])[:300]},
                "answers": [{"poll_media": {"text": a[:55]}} for a in answers_raw],
                "duration": max(1, int(raw_poll.get("duration_hours", 24) or 24)),
                "allow_multiselect": bool(raw_poll.get("allow_multiselect", False)),
                "layout_type": 1,
            }

        channel_id = ""
        try:
            if resolved_target.kind == "user":
                channel_id = await self._ensure_dm_channel_id(resolved_target.value)
            else:
                channel_id = resolved_target.value

            try:
                response = await self._post_json(
                    url=f"{self.api_base}/channels/{channel_id}/messages",
                    payload=payload,
                    error_prefix="discord_send",
                )
            except RuntimeError as exc:
                should_fallback_to_dm = (
                    str(exc) == "discord_send_http_404"
                    and resolved_target.kind == "ambiguous"
                    and self._looks_like_snowflake(resolved_target.value)
                )
                if not should_fallback_to_dm:
                    raise
                original_exc = exc
                try:
                    channel_id = await self._ensure_dm_channel_id(resolved_target.value)
                except Exception:
                    raise original_exc
                response = await self._post_json(
                    url=f"{self.api_base}/channels/{channel_id}/messages",
                    payload=payload,
                    error_prefix="discord_send",
                )

            if response.content:
                try:
                    data = response.json()
                except Exception:
                    data = {}
            else:
                data = {}
            message_id = str(data.get("id", "") or "").strip()
            if not message_id:
                digest = hashlib.sha256(
                    f"{channel_id}:{text}".encode("utf-8")
                ).hexdigest()[:16]
                message_id = f"fallback-{digest}"
            self._last_error = ""
            return f"discord:sent:{message_id}"
        finally:
            if channel_id:
                await self._stop_typing(channel_id)

    async def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> bool:
        """Add a reaction emoji to a message.

        emoji: Unicode emoji (e.g. "👍") or custom emoji name:id (e.g. "name:123456").
        Returns True on success (HTTP 204), False on any error.
        """
        if not self._running:
            return False
        client = self._client
        if client is None:
            return False
        import urllib.parse
        encoded_emoji = urllib.parse.quote(str(emoji or "").strip(), safe="")
        if not encoded_emoji:
            return False
        channel_id = str(channel_id or "").strip()
        message_id = str(message_id or "").strip()
        if not channel_id or not message_id:
            return False
        url = f"{self.api_base}/channels/{channel_id}/messages/{message_id}/reactions/{encoded_emoji}/@me"
        for attempt in range(1, self.send_retry_attempts + 1):
            try:
                response = await client.put(url)
            except Exception as exc:
                self._last_error = str(exc)
                return False
            if response.status_code == 204:
                return True
            if response.status_code == 429:
                self._last_error = "http:429"
                if attempt >= self.send_retry_attempts:
                    return False
                retry_after = self._extract_retry_after(response)
                await asyncio.sleep(retry_after)
                continue
            self._last_error = f"http:{response.status_code}"
            return False
        return False

    async def create_thread(
        self,
        *,
        channel_id: str,
        name: str,
        message_id: str | None = None,
        auto_archive_duration: int = 1440,
    ) -> str:
        """Create a Discord thread.

        If message_id is given, creates a thread anchored to that message.
        Otherwise creates a standalone channel thread.
        Returns the new thread_id or empty string on failure.
        auto_archive_duration: minutes before auto-archive (60, 1440, 4320, 10080).
        """
        channel_id = str(channel_id or "").strip()
        name = str(name or "").strip()[:100]  # Discord limit
        if not channel_id or not name:
            return ""
        if message_id:
            url = f"{self.api_base}/channels/{channel_id}/messages/{message_id}/threads"
        else:
            url = f"{self.api_base}/channels/{channel_id}/threads"
        payload: dict[str, Any] = {
            "name": name,
            "auto_archive_duration": auto_archive_duration,
        }
        try:
            response = await self._post_json(
                url=url,
                payload=payload,
                error_prefix="discord_thread",
            )
            data = response.json() if response.content else {}
            return str(data.get("id", "") or "").strip()
        except Exception as exc:
            self._last_error = str(exc)
            return ""

    async def _gateway_runner(self) -> None:
        backoff_s = self.gateway_backoff_base_s
        while self._running:
            await cancel_task(self._heartbeat_task)
            self._heartbeat_task = None
            connect_url = self._resume_url or self.gateway_url
            try:
                async with websockets.connect(
                    connect_url,
                    open_timeout=self.timeout_s,
                    close_timeout=self.timeout_s,
                    ping_interval=None,
                ) as ws:
                    self._ws = ws
                    self._last_error = ""
                    backoff_s = self.gateway_backoff_base_s
                    await self._gateway_loop()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                if not self._running:
                    break
                await asyncio.sleep(backoff_s)
                backoff_s = min(
                    self.gateway_backoff_max_s,
                    max(self.gateway_backoff_base_s, backoff_s * 2.0),
                )
            finally:
                self._ws = None
                await cancel_task(self._heartbeat_task)
                self._heartbeat_task = None

    async def _gateway_loop(self) -> None:
        ws = self._ws
        if ws is None:
            return
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            should_continue = await self._handle_gateway_payload(data)
            if not should_continue:
                break

    async def _handle_gateway_payload(self, data: dict[str, Any]) -> bool:
        seq = data.get("s")
        if isinstance(seq, int):
            self._sequence = seq

        op = int(data.get("op", -1))
        event_type = str(data.get("t", "") or "").strip().upper()
        payload = data.get("d")

        if op == 10 and isinstance(payload, dict):
            interval_ms = float(payload.get("heartbeat_interval", 45000) or 45000)
            await self._start_heartbeat(interval_ms / 1000.0)
            if self._session_id and self._sequence is not None:
                await self._resume()
            else:
                await self._identify()
            return True

        if op == 11:
            return True

        if op == 1:
            await self._send_ws_json({"op": 1, "d": self._sequence})
            return True

        if op == 7:
            return False

        if op == 9:
            resumable = bool(payload)
            if not resumable:
                self._session_id = ""
                self._resume_url = ""
                self._sequence = None
            return False

        if op != 0 or not isinstance(payload, dict):
            return True

        if event_type == "READY":
            self._session_id = str(payload.get("session_id", "") or "").strip()
            self._resume_url = str(payload.get("resume_gateway_url", "") or "").strip()
            user = payload.get("user")
            if isinstance(user, dict):
                self._bot_user_id = str(user.get("id", "") or "").strip()
            app = payload.get("application")
            if isinstance(app, dict):
                self._application_id = str(app.get("id", "") or "").strip()
            return True

        if event_type == "RESUMED":
            return True

        if event_type == "MESSAGE_CREATE":
            await self._handle_message_create(payload)
            return True

        if event_type == "MESSAGE_REACTION_ADD":
            await self._handle_message_reaction_add(payload)
            return True

        if event_type == "MESSAGE_REACTION_REMOVE":
            return True  # Silently acknowledged

        if event_type == "INTERACTION_CREATE":
            await self._handle_interaction_create(payload)
            return True

        return True

    async def _send_ws_json(self, payload: dict[str, Any]) -> None:
        ws = self._ws
        if ws is None:
            return
        await ws.send(json.dumps(payload))

    async def _identify(self) -> None:
        await self._send_ws_json(
            {
                "op": 2,
                "d": {
                    "token": self.token,
                    "intents": self.gateway_intents,
                    "properties": {
                        "os": "clawlite",
                        "browser": "clawlite",
                        "device": "clawlite",
                    },
                },
            }
        )

    async def _resume(self) -> None:
        if not self._session_id:
            await self._identify()
            return
        await self._send_ws_json(
            {
                "op": 6,
                "d": {
                    "token": self.token,
                    "session_id": self._session_id,
                    "seq": self._sequence,
                },
            }
        )

    async def _start_heartbeat(self, interval_s: float) -> None:
        await cancel_task(self._heartbeat_task)

        async def _heartbeat_loop() -> None:
            while self._running and self._ws is not None:
                await self._send_ws_json({"op": 1, "d": self._sequence})
                await asyncio.sleep(max(0.1, interval_s))

        self._heartbeat_task = asyncio.create_task(_heartbeat_loop())

    @staticmethod
    def _normalize_attachment_rows(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        attachments: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            attachments.append(
                {
                    "id": str(item.get("id", "") or "").strip(),
                    "filename": str(item.get("filename", "") or "").strip(),
                    "url": str(item.get("url", "") or "").strip(),
                    "content_type": str(
                        item.get("content_type", item.get("contentType", "")) or ""
                    ).strip(),
                    "size": int(item.get("size", 0) or 0),
                }
            )
        return attachments

    async def _download_attachment(self, url: str, filename: str = "") -> bytes | None:
        """Download an attachment from Discord CDN. Returns raw bytes or None on failure."""
        url = str(url or "").strip()
        if not url or not url.startswith("https://"):
            return None
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s * 3) as cdn_client:
                response = await cdn_client.get(url)
                if response.status_code == 200:
                    return bytes(response.content)
        except Exception as exc:
            self._last_error = str(exc)
        return None

    async def _handle_message_create(self, payload: dict[str, Any]) -> None:
        author = payload.get("author")
        if not isinstance(author, dict):
            return
        author_id = str(author.get("id", "") or "").strip()
        if not author_id:
            return
        if bool(author.get("bot")) or (
            self._bot_user_id and author_id == self._bot_user_id
        ):
            return

        channel_id = str(payload.get("channel_id", "") or "").strip()
        if not channel_id:
            return

        username = str(author.get("username", "") or "").strip()
        if not self._is_allowed_sender(user_id=author_id, username=username):
            return

        attachments = self._normalize_attachment_rows(payload.get("attachments"))
        content = str(payload.get("content", "") or "").strip()

        # Download attachment bytes concurrently
        attachment_data: list[dict[str, Any]] = []
        if attachments:
            download_tasks = [
                self._download_attachment(row["url"], row["filename"])
                for row in attachments
            ]
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            for row, data in zip(attachments, results):
                entry = dict(row)
                entry["data"] = data if isinstance(data, bytes) else None
                attachment_data.append(entry)

        # Build text
        attachment_desc = " ".join(
            row["filename"] or row["id"] or "file"
            for row in attachments
            if row.get("filename") or row.get("id")
        )
        if content:
            text = content
        elif attachment_desc:
            text = f"[attachments: {attachment_desc}]"
        else:
            text = "[attachment]"

        metadata = {
            "channel": "discord",
            "channel_id": channel_id,
            "guild_id": str(payload.get("guild_id", "") or "").strip(),
            "message_id": str(payload.get("id", "") or "").strip(),
            "author_username": username,
            "author_global_name": str(author.get("global_name", "") or "").strip(),
            "attachments": attachments,
            "attachment_data": attachment_data,
            "is_dm": not bool(payload.get("guild_id")),
        }

        await self._start_typing(channel_id)
        try:
            await self.emit(
                session_id=f"discord:{channel_id}",
                user_id=author_id,
                text=text,
                metadata=metadata,
            )
        finally:
            await self._stop_typing(channel_id)

    async def _handle_message_reaction_add(self, payload: dict[str, Any]) -> None:
        """Handle incoming reaction — emits as metadata-only event for agent awareness."""
        user_id = str(payload.get("user_id", "") or "").strip()
        if not user_id or user_id == self._bot_user_id:
            return
        channel_id = str(payload.get("channel_id", "") or "").strip()
        if not channel_id:
            return
        if not self._is_allowed_sender(user_id=user_id):
            return
        emoji_data = payload.get("emoji") or {}
        emoji_name = str(emoji_data.get("name", "") or "").strip()
        emoji_id = str(emoji_data.get("id", "") or "").strip()
        emoji_str = f"{emoji_name}:{emoji_id}" if emoji_id else emoji_name
        if not emoji_str:
            return
        metadata = {
            "channel": "discord",
            "channel_id": channel_id,
            "guild_id": str(payload.get("guild_id", "") or "").strip(),
            "message_id": str(payload.get("message_id", "") or "").strip(),
            "event_type": "reaction_add",
            "emoji": emoji_str,
        }
        await self.emit(
            session_id=f"discord:{channel_id}",
            user_id=user_id,
            text=f"[reaction: {emoji_str}]",
            metadata=metadata,
        )

    async def _handle_interaction_create(self, payload: dict[str, Any]) -> None:
        """Handle Discord INTERACTION_CREATE — slash commands (type 2) and button clicks (type 3)."""
        interaction_id = str(payload.get("id", "") or "").strip()
        interaction_token = str(payload.get("token", "") or "").strip()
        interaction_type = int(payload.get("type", 0) or 0)
        channel_id = str(payload.get("channel_id", "") or "").strip()
        data = payload.get("data") or {}
        member = payload.get("member") or {}
        user = payload.get("user") or member.get("user") or {}
        user_id = str(user.get("id", "") or "").strip()
        username = str(user.get("username", "") or "").strip()

        if not interaction_id or not interaction_token:
            return

        # ACK the interaction immediately (type 5 = deferred channel message)
        asyncio.create_task(self._ack_interaction(interaction_id, interaction_token))

        if interaction_type == 2:
            # APPLICATION_COMMAND (slash command)
            command_name = str(data.get("name", "") or "").strip()
            options = data.get("options") or []
            args_text = " ".join(
                f"{o.get('name')}={o.get('value')}" for o in options if isinstance(o, dict)
            )
            text = f"/{command_name}" + (f" {args_text}" if args_text else "")
            metadata = {
                "channel": "discord",
                "channel_id": channel_id,
                "update_kind": "slash_command",
                "command_name": command_name,
                "command_options": options,
                "interaction_id": interaction_id,
                "interaction_token": interaction_token,
                "user_id": user_id,
                "username": username,
                "text": text,
            }
            await self.emit(
                session_id=f"discord:{channel_id}",
                user_id=user_id,
                text=text,
                metadata=metadata,
            )

        elif interaction_type == 3:
            # MESSAGE_COMPONENT (button click)
            custom_id = str(data.get("custom_id", "") or "").strip()
            component_type = int(data.get("component_type", 0) or 0)
            message = payload.get("message") or {}
            message_id = str(message.get("id", "") or "").strip()
            text = f"[button:{custom_id}]"
            metadata = {
                "channel": "discord",
                "channel_id": channel_id,
                "update_kind": "button_click",
                "custom_id": custom_id,
                "component_type": component_type,
                "message_id": message_id,
                "interaction_id": interaction_id,
                "interaction_token": interaction_token,
                "user_id": user_id,
                "username": username,
                "text": text,
            }
            await self.emit(
                session_id=f"discord:{channel_id}",
                user_id=user_id,
                text=text,
                metadata=metadata,
            )

    async def _ack_interaction(self, interaction_id: str, interaction_token: str) -> None:
        """Immediately ACK a Discord interaction with deferred response (type 5)."""
        try:
            await self._post_json(
                url=f"{self.api_base}/interactions/{interaction_id}/{interaction_token}/callback",
                payload={"type": 5},
                error_prefix="discord_interaction_ack",
            )
        except Exception:
            pass  # ACK failure is non-fatal; Discord will timeout gracefully

    async def register_slash_command(
        self,
        *,
        name: str,
        description: str,
        options: list[dict[str, Any]] | None = None,
        guild_id: str | None = None,
    ) -> dict[str, Any]:
        """Register (or overwrite) a global or guild slash command."""
        app_id = self._application_id
        if not app_id:
            raise RuntimeError("discord_application_id_unknown — wait for READY event")
        clean_guild = str(guild_id or "").strip()
        if clean_guild:
            url = f"{self.api_base}/applications/{app_id}/guilds/{clean_guild}/commands"
        else:
            url = f"{self.api_base}/applications/{app_id}/commands"
        body: dict[str, Any] = {
            "name": str(name or "").strip(),
            "description": str(description or "").strip(),
            "type": 1,  # CHAT_INPUT
        }
        if options:
            body["options"] = options
        response = await self._post_json(url=url, payload=body, error_prefix="discord_register_slash")
        try:
            return dict(response.json() if response.content else {})
        except Exception:
            return {}

    async def list_slash_commands(self, *, guild_id: str | None = None) -> list[dict[str, Any]]:
        """List registered global or guild slash commands."""
        app_id = self._application_id
        if not app_id:
            return []
        clean_guild = str(guild_id or "").strip()
        if clean_guild:
            url = f"{self.api_base}/applications/{app_id}/guilds/{clean_guild}/commands"
        else:
            url = f"{self.api_base}/applications/{app_id}/commands"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bot {self.token}", "Content-Type": "application/json"},
                )
            return list(response.json() if response.content else [])
        except Exception:
            return []

    async def reply_interaction(
        self,
        *,
        interaction_id: str,
        interaction_token: str,
        text: str,
        components: list[dict[str, Any]] | None = None,
        embeds: list[dict[str, Any]] | None = None,
        ephemeral: bool = False,
    ) -> str:
        """Edit the deferred interaction reply (follow-up to ACK type 5)."""
        url = f"{self.api_base}/webhooks/{self._application_id}/{interaction_token}/messages/@original"
        body: dict[str, Any] = {"content": str(text or "")}
        if components:
            body["components"] = components
        if embeds:
            body["embeds"] = embeds
        if ephemeral:
            body["flags"] = 64  # EPHEMERAL
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.patch(
                    url,
                    json=body,
                    headers={"Authorization": f"Bot {self.token}", "Content-Type": "application/json"},
                )
            data = response.json() if response.content else {}
            return str(data.get("id", "") or "")
        except Exception:
            return ""

    @staticmethod
    def _generate_placeholder_waveform() -> str:
        """Generate a placeholder sine-wave waveform (base64, 256 samples)."""
        import base64
        import math
        samples = [
            min(255, max(0, round(128 + 64 * math.sin((i / DISCORD_VOICE_WAVEFORM_SAMPLES) * math.pi * 8))))
            for i in range(DISCORD_VOICE_WAVEFORM_SAMPLES)
        ]
        return base64.b64encode(bytes(samples)).decode("ascii")

    async def _generate_waveform_from_audio(self, audio_bytes: bytes) -> str:
        """Generate waveform by sampling raw PCM via ffmpeg. Falls back to placeholder."""
        import base64
        import os
        import struct
        import tempfile
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_bytes)
                tmp_in = f.name
            tmp_pcm = tmp_in + ".raw"
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", tmp_in, "-vn", "-f", "s16le",
                "-acodec", "pcm_s16le", "-ac", "1", "-ar", "8000", tmp_pcm,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            if proc.returncode != 0:
                return self._generate_placeholder_waveform()
            with open(tmp_pcm, "rb") as fpcm:
                pcm_data = fpcm.read()
            samples_raw = struct.unpack(f"{len(pcm_data) // 2}h", pcm_data)
            step = max(1, len(samples_raw) // DISCORD_VOICE_WAVEFORM_SAMPLES)
            waveform = []
            for i in range(DISCORD_VOICE_WAVEFORM_SAMPLES):
                chunk = samples_raw[i * step:(i + 1) * step] or (0,)
                avg = sum(abs(s) for s in chunk) / len(chunk)
                waveform.append(min(255, round((avg / 32767) * 255)))
            while len(waveform) < DISCORD_VOICE_WAVEFORM_SAMPLES:
                waveform.append(0)
            return base64.b64encode(bytes(waveform)).decode("ascii")
        except Exception:
            return self._generate_placeholder_waveform()
        finally:
            for p in (tmp_in, tmp_pcm):  # type: ignore[possibly-undefined]
                try:
                    os.unlink(p)
                except Exception:
                    pass

    async def send_voice_message(
        self,
        *,
        channel_id: str,
        audio_bytes: bytes,
        duration_secs: float,
        waveform: str | None = None,
        reply_to_message_id: str | None = None,
        silent: bool = False,
    ) -> str:
        """Send a Discord voice message (OGG/Opus, IS_VOICE_MESSAGE flag).

        Three-step protocol:
        1. POST /channels/{id}/attachments → get upload_url + upload_filename
        2. PUT {upload_url} with audio bytes
        3. POST /channels/{id}/messages with flag 8192 + attachment metadata
        """
        if not channel_id:
            raise ValueError("channel_id is required")
        clean_channel = str(channel_id).strip()
        resolved_waveform = waveform or await self._generate_waveform_from_audio(audio_bytes)

        # Step 1: Request upload URL
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r1 = await client.post(
                f"{self.api_base}/channels/{clean_channel}/attachments",
                json={"files": [{"filename": "voice-message.ogg", "file_size": len(audio_bytes), "id": "0"}]},
                headers={"Authorization": f"Bot {self.token}", "Content-Type": "application/json"},
            )
        r1.raise_for_status()
        attachment_info = r1.json().get("attachments", [{}])[0]
        upload_url = str(attachment_info.get("upload_url", "") or "")
        upload_filename = str(attachment_info.get("upload_filename", "") or "")
        if not upload_url:
            raise RuntimeError("discord_voice_upload_url_missing")

        # Step 2: Upload the audio
        async with httpx.AsyncClient(timeout=max(30.0, self.timeout_s)) as client:
            r2 = await client.put(upload_url, content=audio_bytes, headers={"Content-Type": "audio/ogg"})
        r2.raise_for_status()

        # Step 3: Send message with voice flag
        flags = DISCORD_VOICE_MESSAGE_FLAG
        if silent:
            flags |= (1 << 12)  # SUPPRESS_NOTIFICATIONS
        msg_body: dict[str, Any] = {
            "flags": flags,
            "attachments": [{
                "id": "0",
                "filename": "voice-message.ogg",
                "uploaded_filename": upload_filename,
                "duration_secs": round(float(duration_secs or 0), 2),
                "waveform": resolved_waveform,
            }],
        }
        if reply_to_message_id:
            msg_body["message_reference"] = {
                "message_id": reply_to_message_id,
                "fail_if_not_exists": False,
            }

        response = await self._post_json(
            url=f"{self.api_base}/channels/{clean_channel}/messages",
            payload=msg_body,
            error_prefix="discord_voice_message",
        )
        try:
            data = response.json() if response.content else {}
        except Exception:
            data = {}
        message_id = str(data.get("id", "") or "").strip() or "unknown"
        return f"discord:voice:{message_id}"

    async def create_webhook(
        self, *, channel_id: str, name: str, avatar: str | None = None
    ) -> dict[str, Any]:
        """Create a webhook in a channel. Returns {id, token, name, ...}."""
        body: dict[str, Any] = {"name": str(name or "clawlite").strip()[:80]}
        if avatar:
            body["avatar"] = str(avatar)
        response = await self._post_json(
            url=f"{self.api_base}/channels/{channel_id}/webhooks",
            payload=body,
            error_prefix="discord_create_webhook",
        )
        try:
            return dict(response.json() if response.content else {})
        except Exception:
            return {}

    async def execute_webhook(
        self,
        *,
        webhook_id: str,
        webhook_token: str,
        text: str = "",
        username: str | None = None,
        avatar_url: str | None = None,
        embeds: list[dict[str, Any]] | None = None,
        components: list[dict[str, Any]] | None = None,
    ) -> str:
        """Execute (post via) a webhook. Returns message_id or empty string."""
        body: dict[str, Any] = {"content": str(text or "")}
        if username:
            body["username"] = str(username)[:80]
        if avatar_url:
            body["avatar_url"] = str(avatar_url)
        if embeds:
            body["embeds"] = embeds
        if components:
            body["components"] = components
        response = await self._post_json(
            url=f"{self.api_base}/webhooks/{webhook_id}/{webhook_token}?wait=true",
            payload=body,
            error_prefix="discord_execute_webhook",
        )
        try:
            data = response.json() if response.content else {}
            return str(data.get("id", "") or "")
        except Exception:
            return ""

    async def create_poll(
        self,
        *,
        channel_id: str,
        question: str,
        answers: list[str],
        duration_hours: int = 24,
        allow_multiselect: bool = False,
    ) -> str:
        """Create a Discord poll in a channel. Returns message_id."""
        clean_answers = [str(a).strip()[:55] for a in answers if str(a).strip()][:10]
        payload: dict[str, Any] = {
            "poll": {
                "question": {"text": str(question)[:300]},
                "answers": [{"poll_media": {"text": a}} for a in clean_answers],
                "duration": max(1, int(duration_hours or 24)),
                "allow_multiselect": bool(allow_multiselect),
                "layout_type": 1,
            }
        }
        response = await self._post_json(
            url=f"{self.api_base}/channels/{channel_id}/messages",
            payload=payload,
            error_prefix="discord_create_poll",
        )
        try:
            data = response.json() if response.content else {}
            return str(data.get("id", "") or "")
        except Exception:
            return ""

    async def _patch_json(self, *, url: str, payload: dict[str, Any]) -> httpx.Response:
        """PATCH JSON to Discord API with auth headers."""
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            return await client.patch(
                url,
                json=payload,
                headers={"Authorization": f"Bot {self.token}", "Content-Type": "application/json"},
            )

    async def send_streaming(
        self,
        *,
        channel_id: str,
        chunks: Any,  # AsyncGenerator[ProviderChunk, None]
        min_edit_interval_s: float = 0.8,
    ) -> str:
        """Stream response to Discord: create placeholder message, edit as chunks arrive.

        Args:
            channel_id: target Discord channel
            chunks: async generator yielding ProviderChunk objects
            min_edit_interval_s: minimum seconds between edits (avoid rate limits)
        Returns:
            discord:streamed:{message_id}
        """
        clean_channel = str(channel_id).strip()

        # Create initial placeholder
        response = await self._post_json(
            url=f"{self.api_base}/channels/{clean_channel}/messages",
            payload={"content": "…"},
            error_prefix="discord_stream_create",
        )
        try:
            msg_id = str((response.json() if response.content else {}).get("id", "") or "")
        except Exception:
            msg_id = ""

        if not msg_id:
            return ""

        accumulated = ""
        last_edit_time = 0.0
        last_sent_text = "…"
        edit_url = f"{self.api_base}/channels/{clean_channel}/messages/{msg_id}"

        async for chunk in chunks:
            if chunk.text:
                accumulated = chunk.accumulated or (accumulated + chunk.text)
            now = time.monotonic()
            should_edit = (
                accumulated != last_sent_text
                and (chunk.done or (now - last_edit_time) >= min_edit_interval_s)
            )
            if should_edit and accumulated:
                try:
                    await self._patch_json(url=edit_url, payload={"content": accumulated})
                    last_sent_text = accumulated
                    last_edit_time = now
                except Exception:
                    pass
            if chunk.done:
                break

        # Final edit to ensure complete text
        if accumulated and accumulated != last_sent_text:
            try:
                await self._patch_json(url=edit_url, payload={"content": accumulated})
            except Exception:
                pass

        return f"discord:streamed:{msg_id}"

    async def _typing_loop(self, channel_id: str) -> None:
        client = self._client
        if client is None:
            return
        url = f"{self.api_base}/channels/{channel_id}/typing"
        while self._running:
            try:
                await client.post(url)
            except asyncio.CancelledError:
                raise
            except Exception:
                return
            await asyncio.sleep(self.typing_interval_s)

    async def _start_typing(self, channel_id: str) -> None:
        if not self.typing_enabled:
            return
        if not channel_id:
            return
        existing = self._typing_tasks.get(channel_id)
        if existing is not None and not existing.done():
            return
        self._typing_tasks[channel_id] = asyncio.create_task(
            self._typing_loop(channel_id)
        )

    async def _stop_typing(self, channel_id: str) -> None:
        task = self._typing_tasks.pop(channel_id, None)
        await cancel_task(task)

    @staticmethod
    def _task_state(task: asyncio.Task[Any] | None) -> str:
        if task is None:
            return "stopped"
        if task.cancelled():
            return "cancelled"
        if task.done():
            exc = task.exception()
            return "failed" if exc is not None else "finished"
        return "running"

    def operator_status(self) -> dict[str, Any]:
        gateway_task_state = self._task_state(self._gateway_task)
        heartbeat_task_state = self._task_state(self._heartbeat_task)
        hints: list[str] = []
        if self.on_message is not None and gateway_task_state != "running":
            hints.append("Discord gateway listener is not running; refresh transport to reconnect the gateway loop.")
        if self._last_error:
            hints.append("Discord recorded a recent transport or HTTP error; inspect the error and consider refreshing transport.")
        if not self._session_id and gateway_task_state == "running":
            hints.append("Discord gateway is running without an active session id yet; wait for READY/RESUMED or refresh transport.")
        return {
            "running": bool(self._running),
            "connected": self._ws is not None,
            "gateway_task_state": gateway_task_state,
            "heartbeat_task_state": heartbeat_task_state,
            "session_id": self._session_id,
            "resume_url": self._resume_url,
            "sequence": self._sequence,
            "bot_user_id": self._bot_user_id,
            "dm_cache_size": len(self._dm_channel_ids),
            "typing_tasks": len(self._typing_tasks),
            "last_error": str(self._last_error or ""),
            "hints": hints,
        }

    async def operator_refresh_transport(self) -> dict[str, Any]:
        was_running = bool(self._running)
        was_gateway_running = self._gateway_task is not None and not self._gateway_task.done()
        summary: dict[str, Any] = {
            "ok": True,
            "was_running": was_running,
            "gateway_restarted": False,
            "last_error": "",
        }
        try:
            await cancel_task(self._gateway_task)
            self._gateway_task = None
            await cancel_task(self._heartbeat_task)
            self._heartbeat_task = None
            ws = self._ws
            self._ws = None
            if ws is not None:
                close_fn = getattr(ws, "close", None)
                if callable(close_fn):
                    result = close_fn()
                    if asyncio.iscoroutine(result):
                        await result
            self._session_id = ""
            self._resume_url = ""
            self._sequence = None
            self._bot_user_id = ""
            self._last_error = ""
            if was_running and (self.on_message is not None or was_gateway_running):
                await self.start()
                summary["gateway_restarted"] = True
        except Exception as exc:
            self._last_error = str(exc)
            summary["ok"] = False
            summary["last_error"] = str(exc)
        return summary | {"status": self.operator_status()}

from __future__ import annotations

import asyncio
from typing import Any, Callable

from loguru import logger

from clawlite.bus.events import InboundEvent, OutboundEvent
from clawlite.bus.queue import MessageQueue
from clawlite.channels.base import BaseChannel
from clawlite.channels.dingtalk import DingTalkChannel
from clawlite.channels.discord import DiscordChannel
from clawlite.channels.email import EmailChannel
from clawlite.channels.feishu import FeishuChannel
from clawlite.channels.googlechat import GoogleChatChannel
from clawlite.channels.imessage import IMessageChannel
from clawlite.channels.irc import IRCChannel
from clawlite.channels.matrix import MatrixChannel
from clawlite.channels.mochat import MochatChannel
from clawlite.channels.qq import QQChannel
from clawlite.channels.signal import SignalChannel
from clawlite.channels.slack import SlackChannel
from clawlite.channels.telegram import TelegramChannel
from clawlite.channels.whatsapp import WhatsAppChannel
from clawlite.utils.logging import bind_event, setup_logging

setup_logging()


class EngineProtocol:
    async def run(
        self,
        *,
        session_id: str,
        user_text: str,
        channel: str | None = None,
        chat_id: str | None = None,
        progress_hook=None,
        stop_event=None,
    ): ...

    def request_stop(self, session_id: str) -> bool: ...


class ChannelManager:
    """Owns channel lifecycle and bridges channels <-> bus <-> engine."""

    def __init__(self, *, bus: MessageQueue, engine: EngineProtocol) -> None:
        self.bus = bus
        self.engine = engine
        self._registry: dict[str, type[BaseChannel]] = {
            "telegram": TelegramChannel,
            "discord": DiscordChannel,
            "slack": SlackChannel,
            "whatsapp": WhatsAppChannel,
            "signal": SignalChannel,
            "googlechat": GoogleChatChannel,
            "email": EmailChannel,
            "matrix": MatrixChannel,
            "irc": IRCChannel,
            "imessage": IMessageChannel,
            "dingtalk": DingTalkChannel,
            "feishu": FeishuChannel,
            "mochat": MochatChannel,
            "qq": QQChannel,
        }
        self._channels: dict[str, BaseChannel] = {}
        self._dispatcher_task: asyncio.Task[Any] | None = None
        self._active_tasks: dict[str, set[asyncio.Task[Any]]] = {}

    def register(self, name: str, channel_cls: type[BaseChannel]) -> None:
        self._registry[name] = channel_cls

    async def _on_channel_message(self, session_id: str, user_id: str, text: str, metadata: dict[str, Any]) -> None:
        channel = str(metadata.get("channel", "")).strip() or session_id.split(":", 1)[0]
        bind_event("channel.inbound", session=session_id, channel=channel).debug("inbound message queued user={} chars={}", user_id, len(text))
        await self.bus.publish_inbound(
            InboundEvent(
                channel=channel,
                session_id=session_id,
                user_id=user_id,
                text=text,
                metadata=metadata,
            )
        )

    @staticmethod
    def _is_stop_command(text: str) -> bool:
        return str(text or "").strip().lower() in {"/stop", "stop"}

    @staticmethod
    def _safe_remove_task(store: dict[str, set[asyncio.Task[Any]]], session_id: str, task: asyncio.Task[Any]) -> None:
        group = store.get(session_id)
        if not group:
            return
        group.discard(task)
        if not group:
            store.pop(session_id, None)

    async def _publish_and_send(self, *, event: OutboundEvent) -> None:
        await self.bus.publish_outbound(event)
        channel = self._channels.get(event.channel)
        if channel is None:
            bind_event("channel.dispatch", session=event.session_id, channel=event.channel).error("channel unavailable")
            return
        try:
            await channel.send(target=event.target, text=event.text, metadata=event.metadata)
            bind_event("channel.send", session=event.session_id, channel=event.channel).info("dispatch sent target={}", event.target)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            bind_event("channel.send", session=event.session_id, channel=event.channel).error("dispatch send failed target={} error={}", event.target, exc)

    async def _handle_stop(self, event: InboundEvent) -> None:
        session_id = event.session_id
        self.bus.request_stop(session_id)
        request_stop = getattr(self.engine, "request_stop", None)
        if callable(request_stop):
            request_stop(session_id)

        tasks = list(self._active_tasks.get(session_id, set()))
        cancelled = 0
        for task in tasks:
            if not task.done() and task.cancel():
                cancelled += 1
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        target = str(event.metadata.get("chat_id") or event.user_id)
        text = f"Stopped {cancelled} active task(s)." if cancelled else "No active task to stop."
        await self._publish_and_send(
            event=OutboundEvent(
                channel=event.channel,
                session_id=session_id,
                target=target,
                text=text,
                metadata={"_control": "stop", "cancelled_tasks": cancelled},
            )
        )

    async def _dispatch_event(self, event: InboundEvent) -> None:
        bind_event("channel.dispatch", session=event.session_id, channel=event.channel).debug("dispatch processing target={}", event.user_id)
        target = str(event.metadata.get("chat_id") or event.user_id)

        async def _progress_hook(progress) -> None:
            stage = str(getattr(progress, "stage", "progress") or "progress")
            message = str(getattr(progress, "message", "") or "").strip()
            if not message:
                return
            metadata = {
                "_progress": True,
                "stage": stage,
                "iteration": int(getattr(progress, "iteration", 0) or 0),
            }
            tool_name = str(getattr(progress, "tool_name", "") or "").strip()
            if tool_name:
                metadata["tool"] = tool_name
            extra = getattr(progress, "metadata", None)
            if isinstance(extra, dict):
                metadata.update(extra)
            await self._publish_and_send(
                event=OutboundEvent(
                    channel=event.channel,
                    session_id=event.session_id,
                    target=target,
                    text=message,
                    metadata=metadata,
                )
            )

        try:
            result = await self.engine.run(
                session_id=event.session_id,
                user_text=event.text,
                channel=event.channel,
                chat_id=target,
                progress_hook=_progress_hook,
                stop_event=self.bus.stop_event(event.session_id),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            bind_event("channel.dispatch", session=event.session_id, channel=event.channel).error("dispatch engine failed error={}", exc)
            return
        finally:
            self.bus.clear_stop(event.session_id)

        await self._publish_and_send(
            event=OutboundEvent(
                channel=event.channel,
                session_id=event.session_id,
                target=target,
                text=result.text,
                metadata={"model": getattr(result, "model", "")},
            )
        )

    async def _dispatch_loop(self) -> None:
        while True:
            event = await self.bus.next_inbound()
            if self._is_stop_command(event.text):
                await self._handle_stop(event)
                continue

            task = asyncio.create_task(self._dispatch_event(event))
            bucket = self._active_tasks.setdefault(event.session_id, set())
            bucket.add(task)
            task.add_done_callback(lambda done, sid=event.session_id: self._safe_remove_task(self._active_tasks, sid, done))

    async def start(self, config: dict[str, Any]) -> None:
        channels_cfg = config.get("channels", {}) if isinstance(config, dict) else {}
        for name, row in channels_cfg.items():
            if not isinstance(row, dict):
                continue
            if not row.get("enabled", False):
                continue
            cls = self._registry.get(name)
            if cls is None:
                bind_event("channel.lifecycle", channel=name).error("channel enabled but not registered")
                continue
            bind_event("channel.lifecycle", channel=name).info("channel enabled")
            channel = cls(config=row, on_message=self._on_channel_message)
            self._channels[name] = channel
            await channel.start()
            bind_event("channel.lifecycle", channel=name).info("channel started")

        if self._dispatcher_task is None:
            self._dispatcher_task = asyncio.create_task(self._dispatch_loop())
            bind_event("channel.lifecycle").info("channel dispatcher started")

    async def stop(self) -> None:
        for session_id, tasks in list(self._active_tasks.items()):
            self.bus.request_stop(session_id)
            request_stop = getattr(self.engine, "request_stop", None)
            if callable(request_stop):
                request_stop(session_id)
            for task in list(tasks):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
        self._active_tasks.clear()

        if self._dispatcher_task is not None:
            bind_event("channel.lifecycle").info("channel dispatcher stopping")
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
            self._dispatcher_task = None
            bind_event("channel.lifecycle").info("channel dispatcher stopped")

        for name, channel in list(self._channels.items()):
            bind_event("channel.lifecycle", channel=name).info("channel stopping")
            await channel.stop()
            bind_event("channel.lifecycle", channel=name).info("channel stopped")
        self._channels.clear()

    async def send(self, *, channel: str, target: str, text: str, metadata: dict[str, Any] | None = None) -> str:
        instance = self._channels.get(channel)
        if instance is None:
            raise KeyError(f"channel_not_available:{channel}")
        return await instance.send(target=target, text=text, metadata=metadata or {})

    def status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "running": ch.running,
                "last_error": ch.health().last_error,
            }
            for name, ch in self._channels.items()
        }

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from clawlite.utils.logging import bind_event, setup_logging

setup_logging()

SnapshotCallback = Callable[[], Awaitable[dict[str, Any]] | dict[str, Any]]
RunCallback = Callable[[dict[str, Any]], Awaitable[Any]]
NowMonotonic = Callable[[], float]


class AutonomyService:
    def __init__(
        self,
        *,
        enabled: bool = False,
        interval_s: float = 900,
        cooldown_s: float = 300,
        timeout_s: float = 45.0,
        max_queue_backlog: int = 200,
        session_id: str = "autonomy:system",
        snapshot_callback: SnapshotCallback | None = None,
        run_callback: RunCallback | None = None,
        now_monotonic: NowMonotonic | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.interval_s = max(1.0, float(interval_s))
        self.cooldown_s = max(0.0, float(cooldown_s))
        self.timeout_s = max(0.1, float(timeout_s))
        self.max_queue_backlog = max(0, int(max_queue_backlog))
        self.session_id = str(session_id or "autonomy:system").strip() or "autonomy:system"
        self._snapshot_callback = snapshot_callback
        self._run_callback = run_callback
        self._now_monotonic = now_monotonic or time.monotonic

        self._task: asyncio.Task[Any] | None = None
        self._running = False
        self._cooldown_until = 0.0

        self._ticks = 0
        self._run_attempts = 0
        self._run_success = 0
        self._run_failures = 0
        self._skipped_backlog = 0
        self._skipped_cooldown = 0
        self._skipped_disabled = 0
        self._last_run_at = ""
        self._last_result_excerpt = ""
        self._last_error = ""
        self._consecutive_error_count = 0
        self._last_snapshot: dict[str, Any] = {}

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _excerpt(value: Any, *, max_chars: int = 280) -> str:
        text = str(value or "").strip()
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 3]}..."

    @staticmethod
    def _trim_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        queue_raw = snapshot.get("queue")
        supervisor_raw = snapshot.get("supervisor")
        channels_raw = snapshot.get("channels")

        queue = queue_raw if isinstance(queue_raw, dict) else {}
        supervisor = supervisor_raw if isinstance(supervisor_raw, dict) else {}
        channels = channels_raw if isinstance(channels_raw, dict) else {}

        queue_trimmed = {
            "outbound_size": int(queue.get("outbound_size", 0) or 0),
            "dead_letter_size": int(queue.get("dead_letter_size", 0) or 0),
            "outbound_oldest_age_s": float(queue.get("outbound_oldest_age_s", 0.0) or 0.0),
            "dead_letter_oldest_age_s": float(queue.get("dead_letter_oldest_age_s", 0.0) or 0.0),
        }

        supervisor_trimmed = {
            "running": bool(supervisor.get("running", False)),
            "incident_count": int(supervisor.get("incident_count", 0) or 0),
            "consecutive_error_count": int(supervisor.get("consecutive_error_count", 0) or 0),
        }

        channels_trimmed = {
            "enabled_count": int(channels.get("enabled_count", 0) or 0),
            "running_count": int(channels.get("running_count", 0) or 0),
        }

        return {
            "queue": queue_trimmed,
            "supervisor": supervisor_trimmed,
            "channels": channels_trimmed,
        }

    async def _read_snapshot(self) -> dict[str, Any]:
        if self._snapshot_callback is None:
            trimmed = self._trim_snapshot({})
            self._last_snapshot = trimmed
            return trimmed
        raw = self._snapshot_callback()
        if asyncio.iscoroutine(raw):
            raw = await raw
        snapshot = raw if isinstance(raw, dict) else {}
        trimmed = self._trim_snapshot(snapshot)
        self._last_snapshot = trimmed
        return trimmed

    async def run_once(self, force: bool = False) -> dict[str, Any]:
        self._ticks += 1
        try:
            now = self._now_monotonic()
            snapshot = await self._read_snapshot()
            queue = snapshot.get("queue", {}) if isinstance(snapshot.get("queue"), dict) else {}
            backlog = int(queue.get("outbound_size", 0) or 0) + int(queue.get("dead_letter_size", 0) or 0)

            if not force and not self.enabled:
                self._skipped_disabled += 1
                return self.status()
            if not force and backlog > self.max_queue_backlog:
                self._skipped_backlog += 1
                return self.status()
            if not force and now < self._cooldown_until:
                self._skipped_cooldown += 1
                return self.status()

            if self._run_callback is None:
                self._run_failures += 1
                self._consecutive_error_count += 1
                self._last_error = "autonomy_callback_unavailable"
                self._cooldown_until = now + self.cooldown_s
                return self.status()

            self._run_attempts += 1
            self._last_run_at = self._utc_now_iso()
            self._cooldown_until = now + self.cooldown_s
            result = await asyncio.wait_for(self._run_callback(snapshot), timeout=self.timeout_s)
            self._run_success += 1
            self._last_result_excerpt = self._excerpt(result)
            self._last_error = ""
            self._consecutive_error_count = 0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._run_failures += 1
            self._consecutive_error_count += 1
            self._last_error = str(exc)
            bind_event("autonomy.tick", session=self.session_id).error("autonomy run failed error={}", exc)
        return self.status()

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.run_once(force=False)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._run_failures += 1
                self._consecutive_error_count += 1
                self._last_error = str(exc)
                bind_event("autonomy.tick", session=self.session_id).error("autonomy loop tick failed error={}", exc)
            if not self._running:
                break
            await asyncio.sleep(self.interval_s)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        bind_event("autonomy.lifecycle").info(
            "autonomy started enabled={} interval_s={} cooldown_s={} timeout_s={} max_queue_backlog={} session_id={}",
            self.enabled,
            self.interval_s,
            self.cooldown_s,
            self.timeout_s,
            self.max_queue_backlog,
            self.session_id,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._last_error = str(exc)
        self._task = None
        bind_event("autonomy.lifecycle").info("autonomy stopped")

    def status(self) -> dict[str, Any]:
        cooldown_remaining_s = max(0.0, self._cooldown_until - self._now_monotonic())
        return {
            "running": bool(self._running and self._task is not None),
            "enabled": bool(self.enabled),
            "session_id": self.session_id,
            "interval_s": self.interval_s,
            "cooldown_s": self.cooldown_s,
            "timeout_s": self.timeout_s,
            "max_queue_backlog": self.max_queue_backlog,
            "ticks": self._ticks,
            "run_attempts": self._run_attempts,
            "run_success": self._run_success,
            "run_failures": self._run_failures,
            "skipped_backlog": self._skipped_backlog,
            "skipped_cooldown": self._skipped_cooldown,
            "skipped_disabled": self._skipped_disabled,
            "last_run_at": self._last_run_at,
            "last_result_excerpt": self._last_result_excerpt,
            "last_error": self._last_error,
            "consecutive_error_count": self._consecutive_error_count,
            "last_snapshot": dict(self._last_snapshot),
            "cooldown_remaining_s": round(cooldown_remaining_s, 3),
        }

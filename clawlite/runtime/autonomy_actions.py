from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Any, Awaitable, Callable

ActionExecutor = Callable[..., Any | Awaitable[Any]]


class AutonomyActionController:
    ALLOWLIST = frozenset(
        {
            "validate_provider",
            "validate_channels",
            "diagnostics_snapshot",
            "dead_letter_replay_dry_run",
        }
    )
    DENYLIST_TOKENS = (
        "delete",
        "reset",
        "drop",
        "format",
        "rm",
        "shutdown",
        "reboot",
        "wipe",
        "truncate",
        "destroy",
    )

    def __init__(
        self,
        *,
        max_actions_per_run: int = 1,
        action_cooldown_s: float = 120.0,
        action_rate_limit_per_hour: int = 20,
        max_replay_limit: int = 50,
        now_monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.max_actions_per_run = max(1, int(max_actions_per_run or 1))
        self.action_cooldown_s = max(0.0, float(action_cooldown_s or 0.0))
        self.action_rate_limit_per_hour = max(1, int(action_rate_limit_per_hour or 1))
        self.max_replay_limit = max(1, int(max_replay_limit or 1))
        self._now_monotonic = now_monotonic or time.monotonic
        self._lock = asyncio.Lock()

        self._totals: dict[str, int] = {
            "proposed": 0,
            "executed": 0,
            "succeeded": 0,
            "failed": 0,
            "blocked": 0,
            "parse_errors": 0,
            "rate_limited": 0,
            "cooldown_blocked": 0,
            "unknown_blocked": 0,
        }
        self._per_action: dict[str, dict[str, Any]] = {name: self._new_action_status() for name in self.ALLOWLIST}
        self._recent_audits: list[dict[str, Any]] = []
        self._last_run: dict[str, Any] = {}

    @staticmethod
    def _new_action_status() -> dict[str, Any]:
        return {
            "proposed": 0,
            "executed": 0,
            "succeeded": 0,
            "failed": 0,
            "blocked": 0,
            "rate_limited": 0,
            "cooldown_blocked": 0,
            "last_executed_at": "",
            "_last_exec_monotonic": 0.0,
            "_executed_timestamps": [],
        }

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _excerpt(value: Any, *, max_chars: int = 260) -> str:
        text = str(value or "").strip()
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 3]}..."

    @staticmethod
    def _clean_args(raw_args: Any) -> dict[str, Any]:
        return dict(raw_args) if isinstance(raw_args, dict) else {}

    @classmethod
    def _extract_first_json_object(cls, raw_text: str) -> dict[str, Any] | None:
        text = str(raw_text or "")
        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[idx:])
            except JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return dict(parsed)
        return None

    def _parse_actions(self, raw_text: str) -> tuple[list[dict[str, Any]], bool]:
        text = str(raw_text or "").strip()
        if text == "AUTONOMY_IDLE" or text.startswith("AUTONOMY_IDLE\n"):
            return ([], False)
        payload = self._extract_first_json_object(text)
        if payload is None:
            return ([], True)
        if "actions" in payload:
            raw_actions = payload.get("actions")
            if not isinstance(raw_actions, list):
                return ([], True)
            actions: list[dict[str, Any]] = []
            for row in raw_actions:
                if not isinstance(row, dict):
                    continue
                action_name = str(row.get("action", "") or "").strip()
                if not action_name:
                    continue
                actions.append({"action": action_name, "args": self._clean_args(row.get("args"))})
            return (actions, False)
        action_name = str(payload.get("action", "") or "").strip()
        if not action_name:
            return ([], True)
        return ([{"action": action_name, "args": self._clean_args(payload.get("args"))}], False)

    def _per_action_row(self, action: str) -> dict[str, Any]:
        row = self._per_action.get(action)
        if row is None:
            row = self._new_action_status()
            self._per_action[action] = row
        return row

    def _prune_rate_window(self, row: dict[str, Any], *, now: float) -> list[float]:
        raw = row.get("_executed_timestamps")
        timestamps = list(raw) if isinstance(raw, list) else []
        window_start = now - 3600.0
        pruned = [float(value) for value in timestamps if float(value) >= window_start]
        row["_executed_timestamps"] = pruned
        return pruned

    @classmethod
    def _denylisted(cls, action: str) -> bool:
        lowered = str(action or "").strip().lower()
        for token in cls.DENYLIST_TOKENS:
            if token in lowered:
                return True
        return False

    async def process(self, raw_text: str, executors: dict[str, ActionExecutor]) -> dict[str, Any]:
        async with self._lock:
            now = self._now_monotonic()
            run_started_at = self._utc_now_iso()
            run_audits: list[dict[str, Any]] = []
            run_proposed = 0
            run_executed = 0
            run_succeeded = 0
            run_failed = 0
            run_blocked = 0

            actions, parse_error = self._parse_actions(raw_text)
            if parse_error:
                self._totals["parse_errors"] += 1
                run_blocked += 1

            for index, row in enumerate(actions):
                action = str(row.get("action", "") or "").strip()
                args = self._clean_args(row.get("args"))
                if not action:
                    continue
                run_proposed += 1
                self._totals["proposed"] += 1
                action_row = self._per_action_row(action)
                action_row["proposed"] += 1

                if index >= self.max_actions_per_run:
                    self._totals["blocked"] += 1
                    run_blocked += 1
                    action_row["blocked"] += 1
                    run_audits.append({"action": action, "status": "blocked", "reason": "max_actions_per_run", "args": dict(args)})
                    continue

                if action not in self.ALLOWLIST or self._denylisted(action):
                    self._totals["blocked"] += 1
                    self._totals["unknown_blocked"] += 1
                    run_blocked += 1
                    action_row["blocked"] += 1
                    run_audits.append({"action": action, "status": "blocked", "reason": "unknown_or_denylisted", "args": dict(args)})
                    continue

                timestamps = self._prune_rate_window(action_row, now=now)
                if len(timestamps) >= self.action_rate_limit_per_hour:
                    self._totals["blocked"] += 1
                    self._totals["rate_limited"] += 1
                    run_blocked += 1
                    action_row["blocked"] += 1
                    action_row["rate_limited"] += 1
                    run_audits.append({"action": action, "status": "blocked", "reason": "rate_limited", "args": dict(args)})
                    continue

                last_exec = float(action_row.get("_last_exec_monotonic", 0.0) or 0.0)
                if self.action_cooldown_s > 0 and last_exec > 0 and now < (last_exec + self.action_cooldown_s):
                    self._totals["blocked"] += 1
                    self._totals["cooldown_blocked"] += 1
                    run_blocked += 1
                    action_row["blocked"] += 1
                    action_row["cooldown_blocked"] += 1
                    run_audits.append({"action": action, "status": "blocked", "reason": "cooldown", "args": dict(args)})
                    continue

                if action == "dead_letter_replay_dry_run":
                    raw_limit = args.get("limit", self.max_replay_limit)
                    try:
                        parsed_limit = int(raw_limit)
                    except (TypeError, ValueError):
                        parsed_limit = self.max_replay_limit
                    args["limit"] = max(0, min(self.max_replay_limit, parsed_limit))
                    args["dry_run"] = True

                executor = executors.get(action)
                if not callable(executor):
                    self._totals["failed"] += 1
                    run_failed += 1
                    action_row["failed"] += 1
                    run_audits.append({"action": action, "status": "failed", "reason": "executor_missing", "args": dict(args)})
                    continue

                self._totals["executed"] += 1
                run_executed += 1
                action_row["executed"] += 1
                action_row["_last_exec_monotonic"] = now
                action_row["last_executed_at"] = self._utc_now_iso()
                self._prune_rate_window(action_row, now=now).append(now)

                try:
                    result = executor(**args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    self._totals["succeeded"] += 1
                    run_succeeded += 1
                    action_row["succeeded"] += 1
                    run_audits.append(
                        {
                            "action": action,
                            "status": "succeeded",
                            "args": dict(args),
                            "result_excerpt": self._excerpt(result),
                        }
                    )
                except Exception as exc:
                    self._totals["failed"] += 1
                    run_failed += 1
                    action_row["failed"] += 1
                    run_audits.append(
                        {
                            "action": action,
                            "status": "failed",
                            "args": dict(args),
                            "error": self._excerpt(exc),
                        }
                    )

            if parse_error:
                run_audits.append({"action": "", "status": "parse_error", "reason": "no_valid_action_json"})

            self._recent_audits.extend(
                {
                    "at": run_started_at,
                    "raw_excerpt": self._excerpt(raw_text),
                    **dict(row),
                }
                for row in run_audits
            )
            if len(self._recent_audits) > 25:
                self._recent_audits = self._recent_audits[-25:]

            self._last_run = {
                "at": run_started_at,
                "raw_excerpt": self._excerpt(raw_text),
                "proposed": run_proposed,
                "executed": run_executed,
                "succeeded": run_succeeded,
                "failed": run_failed,
                "blocked": run_blocked,
                "parse_error": bool(parse_error),
                "audits": run_audits,
            }
            return self.status()

    def status(self) -> dict[str, Any]:
        now = self._now_monotonic()
        per_action_out: dict[str, dict[str, Any]] = {}
        for action, row in sorted(self._per_action.items()):
            timestamps = self._prune_rate_window(row, now=now)
            per_action_out[action] = {
                "proposed": int(row.get("proposed", 0) or 0),
                "executed": int(row.get("executed", 0) or 0),
                "succeeded": int(row.get("succeeded", 0) or 0),
                "failed": int(row.get("failed", 0) or 0),
                "blocked": int(row.get("blocked", 0) or 0),
                "rate_limited": int(row.get("rate_limited", 0) or 0),
                "cooldown_blocked": int(row.get("cooldown_blocked", 0) or 0),
                "last_executed_at": str(row.get("last_executed_at", "") or ""),
                "executed_last_hour": len(timestamps),
            }
        return {
            "max_actions_per_run": self.max_actions_per_run,
            "action_cooldown_s": self.action_cooldown_s,
            "action_rate_limit_per_hour": self.action_rate_limit_per_hour,
            "max_replay_limit": self.max_replay_limit,
            "totals": dict(self._totals),
            "per_action": per_action_out,
            "last_run": dict(self._last_run),
            "recent_audits": list(self._recent_audits),
        }

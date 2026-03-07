from __future__ import annotations

"""Tool bridge for executable SKILL.md entries.

`SkillTool` makes discovered skills runnable at runtime without changing
`registry.py` for each new skill:
- `command:` runs shell commands from SKILL metadata
- `script:` dispatches to built-in tool wrappers or external executables
"""

import inspect
import json
import os
import shlex
import shutil
from typing import Any
from urllib.parse import quote_plus

import httpx

from clawlite.core.skills import SkillsLoader
from clawlite.tools.base import Tool, ToolContext
from clawlite.tools.registry import ToolRegistry
from clawlite.utils.logging import bind_event


class SkillTool(Tool):
    """Execute skills discovered by `SkillsLoader`.

    This tool is required to turn SKILL.md discovery into actual execution.
    Without it, skills would appear in prompt context but would not be callable.
    """

    name = "run_skill"
    description = "Execute a discovered SKILL.md binding with deterministic contracts."

    MAX_TIMEOUT_SECONDS = 120.0
    MAX_SKILL_ARGS = 32
    MAX_ARG_CHARS = 4000
    SUMMARY_MAX_SOURCE_CHARS = 12000

    def __init__(
        self,
        *,
        loader: SkillsLoader,
        registry: ToolRegistry,
        memory: Any | None = None,
        provider: Any | None = None,
    ) -> None:
        self.loader = loader
        self.registry = registry
        self.memory = memory
        self.provider = provider

    @staticmethod
    def _policy_reason(raw: Any) -> str:
        text = str(raw or "").strip()
        if not text:
            return "unspecified"
        return text.replace("\n", " ").replace("\r", " ")

    async def _memory_policy_allows(self, *, session_id: str) -> tuple[bool, str]:
        memory = self.memory
        if memory is None:
            return True, ""

        policy_fn = getattr(memory, "integration_policy", None)
        if not callable(policy_fn):
            return True, ""

        try:
            verdict = policy_fn("skill", session_id=session_id)
            if inspect.isawaitable(verdict):
                verdict = await verdict
        except Exception as exc:
            return False, f"policy_exception:{exc.__class__.__name__.lower()}"

        if isinstance(verdict, bool):
            return verdict, "" if verdict else "blocked"

        if isinstance(verdict, dict):
            allowed_raw = verdict.get("allowed", verdict.get("allow", verdict.get("ok", True)))
            allowed = bool(allowed_raw)
            reason = self._policy_reason(verdict.get("reason", verdict.get("message", verdict.get("detail", ""))))
            return allowed, reason if not allowed else ""

        allowed_attr = getattr(verdict, "allowed", None)
        if allowed_attr is not None:
            allowed = bool(allowed_attr)
            reason = self._policy_reason(getattr(verdict, "reason", ""))
            return allowed, reason if not allowed else ""

        return True, ""

    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "input": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "timeout": {"type": "number", "default": 30},
                "query": {"type": "string"},
                "location": {"type": "string"},
                "tool_arguments": {"type": "object"},
            },
            "required": ["name"],
        }

    @staticmethod
    def _extra_args(arguments: dict[str, Any]) -> list[str]:
        values = arguments.get("args")
        if isinstance(values, list):
            return [str(item) for item in values if str(item).strip()]
        raw = str(arguments.get("input", "")).strip()
        return shlex.split(raw) if raw else []

    @classmethod
    def _guard_extra_args(cls, values: list[str]) -> str | None:
        if len(values) > cls.MAX_SKILL_ARGS:
            return f"skill_args_exceeded:max={cls.MAX_SKILL_ARGS}"
        for value in values:
            if len(value) > cls.MAX_ARG_CHARS:
                return f"skill_arg_too_large:max_chars={cls.MAX_ARG_CHARS}"
            if "\x00" in value or "\n" in value or "\r" in value:
                return "skill_arg_invalid_character"
        return None

    @classmethod
    def _timeout_value(cls, arguments: dict[str, Any]) -> float:
        raw = float(arguments.get("timeout", 30) or 30)
        if raw < 1:
            return 1.0
        if raw > cls.MAX_TIMEOUT_SECONDS:
            return cls.MAX_TIMEOUT_SECONDS
        return raw

    @staticmethod
    def _join_command(argv: list[str]) -> str:
        if not argv:
            return ""
        return shlex.join(argv)

    async def _run_command_via_exec_tool(self, *, spec_name: str, argv: list[str], timeout: float, ctx: ToolContext) -> str:
        command = self._join_command(argv)
        if not command:
            raise ValueError("empty command")
        try:
            return await self.registry.execute(
                "exec",
                {"command": command, "timeout": timeout},
                session_id=ctx.session_id,
                channel=ctx.channel,
                user_id=ctx.user_id,
            )
        except RuntimeError as exc:
            error = str(exc)
            if error.startswith("tool_blocked_by_safety_policy:exec:"):
                return f"skill_blocked:{spec_name}:{error}"
            raise

    @staticmethod
    def _exec_output_exit_code(payload: str) -> int | None:
        line = str(payload or "").splitlines()[0:1]
        if not line or not line[0].startswith("exit="):
            return None
        try:
            return int(line[0].split("=", 1)[1].strip())
        except ValueError:
            return None

    @staticmethod
    def _exec_output_stream(payload: str, key: str) -> str:
        prefix = f"{key}="
        for line in str(payload or "").splitlines():
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return ""

    @staticmethod
    def _weather_code_description(code: int) -> str:
        mapping = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "fog",
            48: "rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            71: "slight snow",
            73: "moderate snow",
            75: "heavy snow",
            80: "rain showers",
            81: "strong rain showers",
            82: "violent rain showers",
            95: "thunderstorm",
        }
        return mapping.get(int(code), "unknown")

    async def _run_weather(self, arguments: dict[str, Any]) -> str:
        location = str(arguments.get("location") or arguments.get("input") or "").strip()
        if not location:
            location = "Sao Paulo"
        url = f"https://wttr.in/{quote_plus(location)}?format=3"
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.get(url)
                response.raise_for_status()
            return response.text.strip()
        except Exception:
            async with httpx.AsyncClient(timeout=12) as client:
                geocode = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": location, "count": 1, "language": "en", "format": "json"},
                )
                geocode.raise_for_status()
                geocode_payload = geocode.json()
                results = geocode_payload.get("results", []) if isinstance(geocode_payload, dict) else []
                if not isinstance(results, list) or not results:
                    raise RuntimeError(f"weather_location_not_found:{location}")
                first = results[0] if isinstance(results[0], dict) else {}
                latitude = first.get("latitude")
                longitude = first.get("longitude")
                if latitude is None or longitude is None:
                    raise RuntimeError(f"weather_location_not_found:{location}")
                resolved_name = str(first.get("name", location) or location).strip()
                country = str(first.get("country", "") or "").strip()
                forecast = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current_weather": "true",
                        "timezone": "auto",
                    },
                )
                forecast.raise_for_status()
            forecast_payload = forecast.json()
            current = forecast_payload.get("current_weather", {}) if isinstance(forecast_payload, dict) else {}
            if not isinstance(current, dict) or not current:
                raise RuntimeError("weather_current_unavailable")
            place = resolved_name if not country else f"{resolved_name}, {country}"
            return (
                f"{place}: {current.get('temperature')}°C, "
                f"{self._weather_code_description(int(current.get('weathercode', 0) or 0))}, "
                f"wind {current.get('windspeed')} km/h"
            )

    @staticmethod
    def _script_tool_arguments(script_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = arguments.get("tool_arguments")
        if isinstance(payload, dict):
            return payload

        if script_name == "web_search":
            query = str(arguments.get("query") or arguments.get("input") or "").strip()
            if not query:
                raise ValueError("query or input is required for web-search skill")
            limit = int(arguments.get("limit", 5) or 5)
            return {"query": query, "limit": limit}

        return {}

    async def _precheck_github_auth(self, *, spec_name: str, timeout: float, ctx: ToolContext) -> str | None:
        if os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"):
            return None
        if self.registry.get("exec") is None:
            return None
        result = await self._run_command_via_exec_tool(
            spec_name=spec_name,
            argv=["gh", "auth", "status"],
            timeout=min(timeout, 15.0),
            ctx=ctx,
        )
        if result.startswith(f"skill_blocked:{spec_name}:"):
            return result
        exit_code = self._exec_output_exit_code(result)
        if exit_code is None or exit_code == 0:
            return None
        stderr = self._exec_output_stream(result, "stderr")
        detail = stderr or "gh auth status failed"
        return f"skill_auth_required:{spec_name}:gh:{detail}"

    async def _load_summary_source(self, arguments: dict[str, Any], ctx: ToolContext) -> tuple[str, str]:
        payload = arguments.get("tool_arguments")
        source_input = ""
        if isinstance(payload, dict):
            source_input = str(payload.get("input") or payload.get("url") or payload.get("path") or "").strip()
        if not source_input:
            source_input = str(arguments.get("input") or arguments.get("url") or arguments.get("path") or "").strip()
        if not source_input:
            extra = self._extra_args(arguments)
            source_input = extra[0] if extra else ""
        if not source_input:
            raise ValueError("input is required for summarize skill")

        if source_input.startswith(("http://", "https://")):
            raw = await self.registry.execute(
                "web_fetch",
                {"url": source_input, "max_chars": self.SUMMARY_MAX_SOURCE_CHARS},
                session_id=ctx.session_id,
                channel=ctx.channel,
                user_id=ctx.user_id,
            )
            decoded = json.loads(raw)
            if not decoded.get("ok"):
                message = decoded.get("error", {}).get("message", "web_fetch_failed")
                raise RuntimeError(f"summary_source_fetch_failed:{message}")
            result = decoded.get("result", {})
            return source_input, str(result.get("text", "") or "").strip()

        read_tool_name = "read" if self.registry.get("read") is not None else "read_file"
        if self.registry.get(read_tool_name) is None:
            raise RuntimeError("summary_source_reader_unavailable")
        text = await self.registry.execute(
            read_tool_name,
            {"path": source_input, "allow_large_file": True, "limit": self.SUMMARY_MAX_SOURCE_CHARS},
            session_id=ctx.session_id,
            channel=ctx.channel,
            user_id=ctx.user_id,
        )
        return source_input, str(text or "").strip()

    async def _run_summarize(self, arguments: dict[str, Any], ctx: ToolContext, *, spec_name: str, timeout: float) -> str:
        argv = ["summarize", *self._extra_args(arguments)]
        source_input = str(arguments.get("input") or arguments.get("url") or arguments.get("path") or "").strip()
        if len(argv) == 1 and source_input:
            argv.append(source_input)
        if shutil.which("summarize") is not None and self.registry.get("exec") is not None:
            result = await self._run_command_via_exec_tool(spec_name=spec_name, argv=argv, timeout=timeout, ctx=ctx)
            exit_code = self._exec_output_exit_code(result)
            if exit_code in {None, 0}:
                return result
        if self.provider is None:
            return f"skill_blocked:{spec_name}:provider_unavailable_for_summary"
        source_label, source_text = await self._load_summary_source(arguments, ctx)
        if not source_text:
            return f"skill_blocked:{spec_name}:summary_source_empty"
        response = await self.provider.complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are ClawLite summarizing content. Preserve hard facts, numbers, dates, deadlines, "
                        "owners, and unresolved risks. Be concise and specific."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this source.\nSource: {source_label}\n\n{source_text[:self.SUMMARY_MAX_SOURCE_CHARS]}",
                },
            ],
            tools=[],
            max_tokens=500,
            temperature=0.2,
        )
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            return f"skill_blocked:{spec_name}:provider_empty_summary"
        return text

    async def _dispatch_script(self, script_name: str, arguments: dict[str, Any], ctx: ToolContext, *, spec_name: str) -> str:
        if script_name == "weather":
            return await self._run_weather(arguments)
        if script_name == "summarize":
            return await self._run_summarize(arguments, ctx, spec_name=spec_name, timeout=self._timeout_value(arguments))

        target_tool = self.registry.get(script_name)
        if target_tool is not None and script_name != self.name:
            tool_arguments = self._script_tool_arguments(script_name, arguments)
            try:
                return await self.registry.execute(
                    script_name,
                    tool_arguments,
                    session_id=ctx.session_id,
                    channel=ctx.channel,
                    user_id=ctx.user_id,
                )
            except RuntimeError as exc:
                if str(exc).startswith(f"tool_blocked_by_safety_policy:{script_name}:"):
                    return f"skill_blocked:{spec_name}:{exc}"
                raise

        return f"skill_script_unavailable:{script_name}"

    async def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        name = str(arguments.get("name", "")).strip()
        log = bind_event("tool.skill", session=ctx.session_id, tool=self.name)
        if not name:
            raise ValueError("skill name is required")

        spec = self.loader.get(name)
        if spec is None:
            raise ValueError(f"skill_not_found:{name}")
        if not spec.enabled:
            return f"skill_disabled:{spec.name}"
        if not spec.available:
            details = ", ".join([*spec.missing, *spec.contract_issues])
            return f"skill_unavailable:{spec.name}:{details}"

        extra_args = self._extra_args(arguments)
        args_guard_error = self._guard_extra_args(extra_args)
        if args_guard_error:
            return f"skill_blocked:{spec.name}:{args_guard_error}"

        allowed, reason = await self._memory_policy_allows(session_id=ctx.session_id)
        if not allowed:
            return f"skill_blocked:{spec.name}:memory_policy:{reason}"

        timeout = self._timeout_value(arguments)

        if spec.execution_kind == "command":
            argv = [*spec.execution_argv, *extra_args]
            if spec.execution_argv and spec.execution_argv[0] == "gh":
                auth_error = await self._precheck_github_auth(spec_name=spec.name, timeout=timeout, ctx=ctx)
                if auth_error is not None:
                    return auth_error
            log.info("running skill command skill={}", spec.name)
            if self.registry.get("exec") is not None:
                return await self._run_command_via_exec_tool(spec_name=spec.name, argv=argv, timeout=timeout, ctx=ctx)
            return f"skill_blocked:{spec.name}:exec_tool_not_registered"

        if spec.execution_kind == "script":
            log.info("running skill script skill={} script={}", spec.name, spec.execution_target)
            return await self._dispatch_script(spec.execution_target, arguments, ctx, spec_name=spec.name)

        if spec.execution_kind == "invalid":
            details = ", ".join(spec.contract_issues)
            return f"skill_invalid_contract:{spec.name}:{details}"

        return f"skill_not_executable:{spec.name}"

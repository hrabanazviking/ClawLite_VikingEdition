from __future__ import annotations

from typing import Any

from clawlite.tools.base import Tool, ToolContext


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._total: dict[str, Any] = {
            "executions": 0,
            "successes": 0,
            "failures": 0,
            "unknown_tool": 0,
            "last_error": "",
        }
        self._per_tool: dict[str, dict[str, Any]] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def replace(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schema(self) -> list[dict[str, Any]]:
        return [self._tools[name].export_schema() for name in sorted(self._tools.keys())]

    def _per_tool_metrics(self, name: str) -> dict[str, Any]:
        row = self._per_tool.get(name)
        if row is None:
            row = {
                "executions": 0,
                "successes": 0,
                "failures": 0,
                "last_error": "",
            }
            self._per_tool[name] = row
        return row

    def diagnostics(self) -> dict[str, Any]:
        per_tool: dict[str, dict[str, Any]] = {}
        for name, values in self._per_tool.items():
            if not isinstance(values, dict):
                continue
            per_tool[name] = {
                "executions": int(values.get("executions", 0)),
                "successes": int(values.get("successes", 0)),
                "failures": int(values.get("failures", 0)),
                "last_error": str(values.get("last_error", "")),
            }
        return {
            "total": {
                "executions": int(self._total.get("executions", 0)),
                "successes": int(self._total.get("successes", 0)),
                "failures": int(self._total.get("failures", 0)),
                "unknown_tool": int(self._total.get("unknown_tool", 0)),
                "last_error": str(self._total.get("last_error", "")),
            },
            "per_tool": per_tool,
        }

    async def execute(self, name: str, arguments: dict[str, Any], *, session_id: str, channel: str = "", user_id: str = "") -> str:
        tool = self.get(name)
        if tool is None:
            self._total["unknown_tool"] = int(self._total["unknown_tool"]) + 1
            self._total["failures"] = int(self._total["failures"]) + 1
            self._total["last_error"] = f"unknown tool: {name}"
            raise KeyError(f"unknown tool: {name}")
        self._total["executions"] = int(self._total["executions"]) + 1
        metrics = self._per_tool_metrics(name)
        metrics["executions"] = int(metrics.get("executions", 0)) + 1
        try:
            result = await tool.run(arguments, ToolContext(session_id=session_id, channel=channel, user_id=user_id))
        except Exception as exc:
            self._total["failures"] = int(self._total["failures"]) + 1
            self._total["last_error"] = str(exc)
            metrics["failures"] = int(metrics.get("failures", 0)) + 1
            metrics["last_error"] = str(exc)
            raise
        self._total["successes"] = int(self._total["successes"]) + 1
        self._total["last_error"] = ""
        metrics["successes"] = int(metrics.get("successes", 0)) + 1
        metrics["last_error"] = ""
        return result

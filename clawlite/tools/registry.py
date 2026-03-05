from __future__ import annotations

from typing import Any

from clawlite.config.schema import ToolSafetyPolicyConfig
from clawlite.tools.base import Tool, ToolContext


class ToolRegistry:
    def __init__(self, *, safety: ToolSafetyPolicyConfig | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._safety = safety or ToolSafetyPolicyConfig()

    def _is_blocked_by_safety(self, *, tool_name: str, channel: str) -> bool:
        if not self._safety.enabled:
            return False
        normalized_tool = str(tool_name or "").strip().lower()
        if normalized_tool not in self._safety.risky_tools:
            return False
        normalized_channel = str(channel or "").strip().lower()
        if not normalized_channel:
            return False
        if normalized_channel in self._safety.allowed_channels:
            return False
        return normalized_channel in self._safety.blocked_channels

    def _is_risky_tool(self, tool_name: str) -> bool:
        return str(tool_name or "").strip().lower() in self._safety.risky_tools

    def _has_channel_restrictions(self) -> bool:
        return bool(self._safety.allowed_channels or self._safety.blocked_channels)

    @staticmethod
    def _derive_channel_from_session(session_id: str) -> str:
        raw = str(session_id or "").strip().lower()
        if not raw:
            return ""
        if ":" not in raw:
            return ""
        return raw.split(":", 1)[0].strip()

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

    async def execute(self, name: str, arguments: dict[str, Any], *, session_id: str, channel: str = "", user_id: str = "") -> str:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        resolved_channel = str(channel or "").strip().lower() or self._derive_channel_from_session(session_id)
        if not resolved_channel and self._safety.enabled and self._is_risky_tool(name) and self._has_channel_restrictions():
            raise RuntimeError(f"tool_blocked_by_safety_policy:{name}:unknown")
        if self._is_blocked_by_safety(tool_name=name, channel=resolved_channel):
            raise RuntimeError(f"tool_blocked_by_safety_policy:{name}:{resolved_channel}")
        return await tool.run(arguments, ToolContext(session_id=session_id, channel=resolved_channel, user_id=user_id))

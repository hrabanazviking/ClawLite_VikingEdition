from __future__ import annotations

import asyncio

from clawlite.tools.base import Tool, ToolContext
from clawlite.tools.registry import ToolRegistry


class EchoTool(Tool):
    name = "echo"
    description = "echo"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return str(arguments.get("text", ""))


def test_tool_registry_execute() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(EchoTool())
        out = await reg.execute("echo", {"text": "ok"}, session_id="s")
        assert out == "ok"

    asyncio.run(_scenario())


def test_tool_registry_diagnostics_tracks_success_and_unknown_tool() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(EchoTool())

        out = await reg.execute("echo", {"text": "ok"}, session_id="s")
        assert out == "ok"

        try:
            await reg.execute("missing", {}, session_id="s")
            raise AssertionError("expected unknown tool error")
        except KeyError:
            pass

        diag = reg.diagnostics()
        assert diag["total"]["executions"] == 1
        assert diag["total"]["successes"] == 1
        assert diag["total"]["failures"] == 1
        assert diag["total"]["unknown_tool"] == 1
        assert "unknown tool: missing" in diag["total"]["last_error"]
        assert diag["per_tool"]["echo"]["executions"] == 1
        assert diag["per_tool"]["echo"]["successes"] == 1
        assert diag["per_tool"]["echo"]["failures"] == 0

    asyncio.run(_scenario())

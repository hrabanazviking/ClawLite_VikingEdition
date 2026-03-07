from __future__ import annotations

import asyncio

from clawlite.config.schema import ToolSafetyLayerConfig, ToolSafetyPolicyConfig
from clawlite.tools.base import Tool, ToolContext
from clawlite.tools.registry import ToolRegistry


class EchoTool(Tool):
    name = "echo"
    description = "echo"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"text": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return str(arguments.get("text", ""))


class ExecLikeTool(Tool):
    name = "exec"
    description = "exec"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"command": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return f"channel={ctx.channel};user={ctx.user_id}"


class RunSkillLikeTool(Tool):
    name = "run_skill"
    description = "run skill"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"name": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return f"skill={arguments.get('name', '')}"


class StrictSchemaTool(Tool):
    name = "strict"
    description = "strict schema validation"

    def args_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "count": {"type": "integer", "minimum": 1, "maximum": 3},
                "mode": {"type": "string", "enum": ["fast", "safe"]},
            },
            "required": ["path", "count"],
            "additionalProperties": False,
        }

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        del ctx
        return f"{arguments['path']}:{arguments['count']}:{arguments.get('mode', '')}"


def test_tool_registry_execute() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(EchoTool())
        out = await reg.execute("echo", {"text": "ok"}, session_id="s")
        assert out == "ok"

    asyncio.run(_scenario())


def test_tool_registry_blocks_risky_tools_for_blocked_channels() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(ExecLikeTool())
        try:
            await reg.execute("exec", {"command": "id"}, session_id="telegram:1", channel="telegram", user_id="1")
            raise AssertionError("expected safety policy block")
        except RuntimeError as exc:
            assert str(exc) == "tool_blocked_by_safety_policy:exec:telegram"

    asyncio.run(_scenario())


def test_tool_registry_blocks_risky_tools_with_derived_channel_from_session() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(ExecLikeTool())
        try:
            await reg.execute("exec", {"command": "id"}, session_id="telegram:1", user_id="1")
            raise AssertionError("expected safety policy block")
        except RuntimeError as exc:
            assert str(exc) == "tool_blocked_by_safety_policy:exec:telegram"

    asyncio.run(_scenario())


def test_tool_registry_blocks_risky_tools_for_unknown_channel_when_restricted() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(ExecLikeTool())
        try:
            await reg.execute("exec", {"command": "id"}, session_id="", channel="", user_id="1")
            raise AssertionError("expected safety policy block")
        except RuntimeError as exc:
            assert str(exc) == "tool_blocked_by_safety_policy:exec:unknown"

    asyncio.run(_scenario())


def test_tool_registry_allows_risky_tools_for_cli_channel() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(ExecLikeTool())
        out = await reg.execute("exec", {"command": "id"}, session_id="cli:1", channel="cli", user_id="1")
        assert out == "channel=cli;user=1"

    asyncio.run(_scenario())


def test_tool_registry_allows_non_risky_tools_for_empty_channel_and_session() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(EchoTool())
        out = await reg.execute("echo", {"text": "ok"}, session_id="", channel="", user_id="")
        assert out == "ok"

    asyncio.run(_scenario())


def test_tool_registry_default_safety_allows_run_skill_for_telegram() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(RunSkillLikeTool())
        out = await reg.execute("run_skill", {"name": "echo"}, session_id="telegram:1", channel="telegram", user_id="1")
        assert out == "skill=echo"

    asyncio.run(_scenario())


def test_tool_registry_blocks_run_skill_for_telegram_when_explicitly_configured() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["run_skill"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(RunSkillLikeTool())
        try:
            await reg.execute("run_skill", {"name": "echo"}, session_id="telegram:1", channel="telegram", user_id="1")
            raise AssertionError("expected safety policy block")
        except RuntimeError as exc:
            assert str(exc) == "tool_blocked_by_safety_policy:run_skill:telegram"

    asyncio.run(_scenario())


def test_tool_registry_layered_profile_override_changes_effective_risky_tools() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
                profile="ops",
                profiles={
                    "ops": ToolSafetyLayerConfig(
                        risky_tools=["run_skill"],
                    )
                },
            )
        )
        reg.register(ExecLikeTool())
        out = await reg.execute("exec", {"command": "id"}, session_id="telegram:1", channel="telegram", user_id="1")
        assert out == "channel=telegram;user=1"

    asyncio.run(_scenario())


def test_tool_registry_layered_agent_override_supersedes_profile_and_global() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
                profile="ops",
                profiles={
                    "ops": ToolSafetyLayerConfig(
                        risky_tools=["exec"],
                        blocked_channels=["telegram"],
                    )
                },
                by_agent={
                    "alpha": ToolSafetyLayerConfig(
                        risky_tools=["exec"],
                        blocked_channels=["slack"],
                    )
                },
            )
        )
        reg.register(ExecLikeTool())
        out = await reg.execute("exec", {"command": "id"}, session_id="agent:alpha:42", channel="telegram", user_id="1")
        assert out == "channel=telegram;user=1"

    asyncio.run(_scenario())


def test_tool_registry_layered_channel_override_supersedes_agent_and_global() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
                by_agent={
                    "alpha": ToolSafetyLayerConfig(
                        blocked_channels=["telegram"],
                    )
                },
                by_channel={
                    "telegram": ToolSafetyLayerConfig(
                        blocked_channels=[],
                    )
                },
            )
        )
        reg.register(ExecLikeTool())
        out = await reg.execute("exec", {"command": "id"}, session_id="agent:alpha:42", channel="telegram", user_id="1")
        assert out == "channel=telegram;user=1"

    asyncio.run(_scenario())


def test_tool_registry_blocks_non_object_arguments_fail_closed() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(StrictSchemaTool())
        try:
            await reg.execute("strict", ["bad"], session_id="cli:1")  # type: ignore[arg-type]
            raise AssertionError("expected argument validation block")
        except RuntimeError as exc:
            assert str(exc) == "tool_invalid_arguments:strict:expected_object"

    asyncio.run(_scenario())


def test_tool_registry_blocks_missing_required_arguments_fail_closed() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(StrictSchemaTool())
        try:
            await reg.execute("strict", {"path": "demo.txt"}, session_id="cli:1")
            raise AssertionError("expected missing required validation block")
        except RuntimeError as exc:
            assert str(exc) == "tool_invalid_arguments:strict:missing_required:count"

    asyncio.run(_scenario())


def test_tool_registry_blocks_type_and_range_mismatches_fail_closed() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(StrictSchemaTool())
        try:
            await reg.execute("strict", {"path": "demo.txt", "count": 0}, session_id="cli:1")
            raise AssertionError("expected range validation block")
        except RuntimeError as exc:
            assert str(exc) == "tool_invalid_arguments:strict:count:minimum_1"

        try:
            await reg.execute("strict", {"path": "demo.txt", "count": "2"}, session_id="cli:1")  # type: ignore[dict-item]
            raise AssertionError("expected type validation block")
        except RuntimeError as exc:
            assert str(exc) == "tool_invalid_arguments:strict:count:expected_integer"

    asyncio.run(_scenario())


def test_tool_registry_blocks_unexpected_arguments_when_schema_forbids_them() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(StrictSchemaTool())
        try:
            await reg.execute(
                "strict",
                {"path": "demo.txt", "count": 2, "extra": True},
                session_id="cli:1",
            )
            raise AssertionError("expected unexpected-argument validation block")
        except RuntimeError as exc:
            assert str(exc) == "tool_invalid_arguments:strict:unexpected_arguments:extra"

    asyncio.run(_scenario())


def test_tool_registry_allows_valid_arguments_after_schema_validation() -> None:
    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(StrictSchemaTool())
        out = await reg.execute(
            "strict",
            {"path": "demo.txt", "count": 2, "mode": "safe"},
            session_id="cli:1",
        )
        assert out == "demo.txt:2:safe"

    asyncio.run(_scenario())

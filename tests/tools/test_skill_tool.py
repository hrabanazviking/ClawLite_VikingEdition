from __future__ import annotations

import asyncio
import json
from pathlib import Path

from clawlite.providers.base import LLMResult
from clawlite.config.schema import ToolSafetyPolicyConfig
from clawlite.core.skills import SkillsLoader
from clawlite.tools.base import Tool, ToolContext
from clawlite.tools.registry import ToolRegistry
from clawlite.tools.skill import SkillTool


class FakeWebSearchTool(Tool):
    name = "web_search"
    description = "fake web search"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return f"query:{arguments.get('query', '')}:{ctx.session_id}:{ctx.channel}:{ctx.user_id}"


class FakeExecTool(Tool):
    name = "exec"
    description = "fake exec"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"command": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return f"exec:{arguments.get('command', '')}:{ctx.channel}:{ctx.user_id}"


class FakeExecStatusTool(Tool):
    name = "exec"
    description = "fake exec with explicit status"

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"command": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        del ctx
        command = str(arguments.get("command", "") or "")
        return self.responses.get(command, f"exit=0\nstdout={command}\nstderr=")


class FakeExecCaptureTool(Tool):
    name = "exec"
    description = "fake exec with captured env overrides"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def args_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "env": {"type": "object"},
            },
        }

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        del ctx
        self.calls.append(dict(arguments))
        payload = arguments.get("env", {})
        env_value = ""
        if isinstance(payload, dict):
            env_value = str(payload.get("GH_TOKEN", payload.get("CUSTOM_TOKEN", "")) or "")
        return f"exit=0\nstdout={env_value}\nstderr="


class FakeWebFetchPayloadTool(Tool):
    name = "web_fetch"
    description = "fake web fetch"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"url": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        del ctx
        url = str(arguments.get("url", "") or "")
        return json.dumps(
            {
                "ok": True,
                "tool": "web_fetch",
                "result": {"text": f"Fetched content from {url}"},
            }
        )


class FakeWebFetchSequenceTool(Tool):
    name = "web_fetch"
    description = "fake ordered web fetch"

    def __init__(self, responses: list[tuple[str, dict[str, object] | str]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"url": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        del ctx
        url = str(arguments.get("url", "") or "")
        self.calls.append(
            {
                "url": url,
                "mode": str(arguments.get("mode", "") or ""),
                "max_chars": int(arguments.get("max_chars", 0) or 0),
            }
        )
        if not self.responses:
            raise AssertionError(f"unexpected web_fetch call: {url}")
        expected_url, payload = self.responses.pop(0)
        assert url == expected_url
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=False)


class FakeReadTool(Tool):
    name = "read"
    description = "fake read"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        del ctx
        return f"Local content from {arguments.get('path', '')}"


class FakeSessionsSpawnTool(Tool):
    name = "sessions_spawn"
    description = "fake sessions spawn"

    def args_schema(self) -> dict:
        return {"type": "object", "properties": {"task": {"type": "string"}}}

    async def run(self, arguments: dict, ctx: ToolContext) -> str:
        return json.dumps(
            {
                "status": "ok",
                "session_id": ctx.session_id,
                "user_id": ctx.user_id,
                "task": arguments.get("task", ""),
                "tasks": arguments.get("tasks", []),
                "share_scope": arguments.get("share_scope", ""),
            }
        )


class FakeProvider:
    async def complete(self, *, messages, tools, max_tokens=None, temperature=None, reasoning_effort=None):
        del tools, max_tokens, temperature, reasoning_effort
        return LLMResult(model="fake/summary", text=f"summary::{messages[-1]['content'].splitlines()[1]}")


class FakeMemory:
    def __init__(self, verdict):
        self.verdict = verdict
        self.calls: list[tuple[str, str]] = []

    def integration_policy(self, kind: str, *, session_id: str):
        self.calls.append((kind, session_id))
        return self.verdict


class ExplodingMemory:
    def integration_policy(self, kind: str, *, session_id: str):
        del kind, session_id
        raise RuntimeError("policy backend unavailable")


def _write_skill(root: Path, slug: str, frontmatter: str, body: str = "body") -> None:
    skill_dir = root / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


def test_run_skill_executes_command_binding(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        'name: echo-skill\ndescription: echo\nalways: false\ncommand: echo',
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        reg.register(tool)
        out = await tool.run(
            {"name": "echo-skill", "input": "hello world"},
            ToolContext(session_id="s1"),
        )
        assert out == "exec:echo hello world::"

    asyncio.run(_scenario())


def test_run_skill_respects_unavailable_requirements(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "blocked",
        'name: blocked\ndescription: blocked\nmetadata: {"nanobot":{"requires":{"bins":["definitely-missing-bin-xyz"]}}}',
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run({"name": "blocked"}, ToolContext(session_id="s2"))
        assert out.startswith("skill_unavailable:blocked")

    asyncio.run(_scenario())


def test_run_skill_blocks_disabled_skill(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        loader = SkillsLoader(builtin_root=tmp_path, state_path=tmp_path / "skills-state.json")
        loader.set_enabled("echo-skill", False)
        tool = SkillTool(loader=loader, registry=reg)
        out = await tool.run(
            {"name": "echo-skill", "input": "hello"},
            ToolContext(session_id="s-disabled"),
        )
        assert out == "skill_disabled:echo-skill"

    asyncio.run(_scenario())


def test_run_skill_dispatches_script_to_tool_registry(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "web",
        "name: web\ndescription: web\nscript: web_search",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeWebSearchTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        reg.register(tool)
        out = await tool.run(
            {"name": "web", "query": "nanobot"},
            ToolContext(session_id="s3", channel="cli", user_id="u3"),
        )
        assert out == "query:nanobot:s3:cli:u3"

    asyncio.run(_scenario())


def test_run_skill_script_respects_channel_safety_policy(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "web",
        "name: web\ndescription: web\nscript: web_search",
    )

    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["web_search"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(FakeWebSearchTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        reg.register(tool)
        out = await tool.run(
            {"name": "web", "query": "nanobot"},
            ToolContext(session_id="s3", channel="telegram", user_id="u3"),
        )
        assert out == "skill_blocked:web:tool_blocked_by_safety_policy:web_search:telegram"

    asyncio.run(_scenario())


def test_run_skill_returns_not_executable_when_no_binding(tmp_path: Path) -> None:
    _write_skill(tmp_path, "doc-only", "name: doc-only\ndescription: doc only")

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run({"name": "doc-only"}, ToolContext(session_id="s4"))
        assert out == "skill_not_executable:doc-only"

    asyncio.run(_scenario())


def test_run_skill_does_not_fallback_to_external_script_exec(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "external-script",
        "name: external-script\ndescription: external\nscript: external_tool",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run({"name": "external-script"}, ToolContext(session_id="s5"))
        assert out == "skill_script_unavailable:external_tool"

    asyncio.run(_scenario())


def test_run_skill_blocks_oversized_argument_list(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "echo-skill", "args": [str(i) for i in range(33)]},
            ToolContext(session_id="s6"),
        )
        assert out == "skill_blocked:echo-skill:skill_args_exceeded:max=32"

    asyncio.run(_scenario())


def test_run_skill_blocks_command_when_exec_tool_not_registered(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "dangerous",
        "name: dangerous\ndescription: dangerous\ncommand: rm",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "dangerous", "args": ["-rf", "/"]},
            ToolContext(session_id="s7", channel="cli", user_id="u1"),
        )
        assert out == "skill_blocked:dangerous:exec_tool_not_registered"

    asyncio.run(_scenario())


def test_run_skill_returns_skill_blocked_when_registry_blocks_exec(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "echo-skill", "args": ["hello"]},
            ToolContext(session_id="telegram:skill", channel="telegram", user_id="42"),
        )
        assert out == "skill_blocked:echo-skill:tool_blocked_by_safety_policy:exec:telegram"

    asyncio.run(_scenario())


def test_run_skill_returns_skill_blocked_when_registry_blocks_exec_unknown_channel(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["exec"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "echo-skill", "args": ["hello"]},
            ToolContext(session_id="skill", channel="", user_id="42"),
        )
        assert out == "skill_blocked:echo-skill:tool_blocked_by_safety_policy:exec:unknown"

    asyncio.run(_scenario())


def test_run_skill_returns_skill_requires_approval_when_registry_requires_exec_approval(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=[],
                approval_specifiers=["exec:echo"],
                approval_channels=["telegram"],
                blocked_channels=[],
                allowed_channels=[],
            )
        )
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "echo-skill", "args": ["hello"]},
            ToolContext(session_id="telegram:skill", channel="telegram", user_id="42"),
        )
        assert out == "skill_requires_approval:echo-skill:tool_requires_approval:exec:telegram"

    asyncio.run(_scenario())


def test_run_skill_command_uses_exec_tool_in_cli_context(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "echo-skill", "args": ["hello world"]},
            ToolContext(session_id="cli:skill", channel="cli", user_id="7"),
        )
        assert out == "exec:echo 'hello world':cli:7"

    asyncio.run(_scenario())


def test_run_skill_command_prefix_dispatches_multiword_binding(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "gh-issues",
        "name: gh-issues\ndescription: gh issue wrapper\ncommand: gh issue",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "gh-issues", "args": ["list", "--repo", "openclaw/openclaw", "--limit", "5"]},
            ToolContext(session_id="cli:gh-issues", channel="cli", user_id="11"),
        )
        assert out == "exec:gh issue list --repo openclaw/openclaw --limit 5:cli:11"

    asyncio.run(_scenario())


def test_run_skill_command_injects_skill_entry_env_overrides(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "env-skill",
        'name: env-skill\ndescription: env skill\ncommand: echo\nmetadata: {"openclaw":{"primaryEnv":"CUSTOM_TOKEN"}}',
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "skills": {
                    "entries": {
                        "env-skill": {
                            "apiKey": "skill-secret",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    async def _scenario() -> None:
        monkeypatch.setenv("CLAWLITE_CONFIG", str(config_path))
        monkeypatch.delenv("CUSTOM_TOKEN", raising=False)
        reg = ToolRegistry()
        exec_tool = FakeExecCaptureTool()
        reg.register(exec_tool)
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "env-skill", "input": "hello"},
            ToolContext(session_id="cli:env-skill", channel="cli", user_id="7"),
        )
        assert out == "exit=0\nstdout=skill-secret\nstderr="
        assert exec_tool.calls[0]["env"] == {"CUSTOM_TOKEN": "skill-secret"}

    asyncio.run(_scenario())


def test_run_skill_gh_issues_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "gh-issues",
        "name: gh-issues\ndescription: gh issue helper\nscript: gh_issues",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "gh-issues"},
            ToolContext(session_id="cli:gh-issues", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert payload["backend"] == "gh issue"
        assert "list" in payload["available_actions"]
        assert "comment" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_gh_issues_structured_list_dispatches_gh_issue(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "gh-issues",
        "name: gh-issues\ndescription: gh issue helper\nscript: gh_issues",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "gh auth status": "exit=0\nstdout=ok\nstderr=",
                    "gh issue list --repo openclaw/openclaw --state open --label bug,high --limit 10": (
                        "exit=0\nstdout=list ok\nstderr="
                    ),
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "gh-issues",
                "tool_arguments": {
                    "action": "list",
                    "repo": "openclaw/openclaw",
                    "state": "open",
                    "labels": ["bug", "high"],
                    "limit": 10,
                },
            },
            ToolContext(session_id="cli:gh-issues", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=list ok\nstderr="

    asyncio.run(_scenario())


def test_run_skill_gh_issues_uses_skill_entry_api_key_for_auth(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "gh-issues",
        'name: gh-issues\ndescription: gh issue helper\nscript: gh_issues\nmetadata: {"openclaw":{"primaryEnv":"GH_TOKEN"}}',
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "skills": {
                    "entries": {
                        "gh-issues": {
                            "apiKey": "skill-gh-token",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    async def _scenario() -> None:
        monkeypatch.setenv("CLAWLITE_CONFIG", str(config_path))
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        reg = ToolRegistry()
        exec_tool = FakeExecCaptureTool()
        reg.register(exec_tool)
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "gh-issues",
                "tool_arguments": {
                    "action": "list",
                    "repo": "openclaw/openclaw",
                    "state": "open",
                    "limit": 5,
                },
            },
            ToolContext(session_id="cli:gh-issues", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=skill-gh-token\nstderr="
        assert len(exec_tool.calls) == 1
        assert exec_tool.calls[0]["command"] == "gh issue list --repo openclaw/openclaw --state open --limit 5"
        assert exec_tool.calls[0]["env"] == {"GH_TOKEN": "skill-gh-token"}

    asyncio.run(_scenario())


def test_run_skill_github_issues_alias_uses_gh_issues_script(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "github-issues",
        "name: github-issues\ndescription: gh issue helper alias\nscript: gh_issues",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "github-issues", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:github-issues", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["backend"] == "gh issue"
        assert "list" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_github_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "github",
        "name: github\ndescription: github helper\nscript: github",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "github"},
            ToolContext(session_id="cli:github", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert payload["backend"] == "gh"
        assert "list_prs" in payload["available_actions"]
        assert "api" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_github_list_prs_dispatches_gh_pr_list(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "github",
        "name: github\ndescription: github helper\nscript: github",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "gh auth status": "exit=0\nstdout=ok\nstderr=",
                    "gh pr list --repo openclaw/openclaw --state open --author bot --label bug,high --limit 25": "exit=0\nstdout=prs ok\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "github",
                "tool_arguments": {
                    "action": "list_prs",
                    "repo": "openclaw/openclaw",
                    "state": "open",
                    "author": "bot",
                    "labels": ["bug", "high"],
                    "limit": 25,
                },
            },
            ToolContext(session_id="cli:github", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=prs ok\nstderr="

    asyncio.run(_scenario())


def test_run_skill_github_api_dispatches_gh_api(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "github",
        "name: github\ndescription: github helper\nscript: github",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "gh auth status": "exit=0\nstdout=ok\nstderr=",
                    "gh api repos/openclaw/openclaw/pulls --method GET --repo openclaw/openclaw": "exit=0\nstdout=api ok\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "github",
                "tool_arguments": {
                    "action": "api",
                    "repo": "openclaw/openclaw",
                    "path": "repos/openclaw/openclaw/pulls",
                    "method": "GET",
                },
            },
            ToolContext(session_id="cli:github", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=api ok\nstderr="

    asyncio.run(_scenario())


def test_run_skill_clawhub_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "clawhub",
        "name: clawhub\ndescription: clawhub helper\nscript: clawhub",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "clawhub", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:clawhub", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert "search" in payload["available_actions"]
        assert "install" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_clawhub_install_dispatches_npx_command(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "clawhub",
        "name: clawhub\ndescription: clawhub helper\nscript: clawhub",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "npx --yes clawhub@latest install weather --workdir /tmp/workspace": "exit=0\nstdout=installed\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "clawhub",
                "tool_arguments": {
                    "action": "install",
                    "slug": "weather",
                    "workdir": "/tmp/workspace",
                },
            },
            ToolContext(session_id="cli:clawhub", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=installed\nstderr="

    asyncio.run(_scenario())


def test_run_skill_hub_alias_uses_clawhub_script(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "hub",
        "name: hub\ndescription: clawhub alias\nscript: clawhub",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "npx --yes clawhub@latest list --workdir /tmp/workspace": "exit=0\nstdout=list ok\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "hub",
                "tool_arguments": {
                    "action": "list",
                    "workdir": "/tmp/workspace",
                },
            },
            ToolContext(session_id="cli:hub", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=list ok\nstderr="

    asyncio.run(_scenario())


def test_run_skill_onepassword_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "1password",
        "name: 1password\ndescription: onepassword helper\nscript: onepassword",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "1password", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:op", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["backend"] == "op"
        assert "item_get" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_onepassword_item_get_dispatches_op_command(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "1password",
        "name: 1password\ndescription: onepassword helper\nscript: onepassword",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "op item get 'GitHub Token' --vault Private --fields label=password": "exit=0\nstdout=secret\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "1password",
                "tool_arguments": {
                    "action": "item_get",
                    "item": "GitHub Token",
                    "vault": "Private",
                    "field": "password",
                },
            },
            ToolContext(session_id="cli:op", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=secret\nstderr="

    asyncio.run(_scenario())


def test_run_skill_docker_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "docker",
        "name: docker\ndescription: docker helper\nscript: docker",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "docker", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:docker", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["backend"] == "docker"
        assert "compose_up" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_docker_logs_dispatches_docker_command(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "docker",
        "name: docker\ndescription: docker helper\nscript: docker",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "docker logs api --tail 200": "exit=0\nstdout=logs\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "docker",
                "tool_arguments": {
                    "action": "logs",
                    "target": "api",
                    "tail": 200,
                },
            },
            ToolContext(session_id="cli:docker", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=logs\nstderr="

    asyncio.run(_scenario())


def test_run_skill_apple_notes_guide_mode_returns_structured_help(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "apple-notes",
        "name: apple-notes\ndescription: apple notes helper\nscript: apple_notes",
    )

    async def _scenario() -> None:
        monkeypatch.setattr("clawlite.tools.skill.sys.platform", "darwin")
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "apple-notes", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:notes", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["platform"] == "darwin"
        assert "read" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_apple_notes_blocks_on_non_macos(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "apple-notes",
        "name: apple-notes\ndescription: apple notes helper\nscript: apple_notes",
    )

    async def _scenario() -> None:
        monkeypatch.setattr("clawlite.tools.skill.sys.platform", "win32")
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "apple-notes", "tool_arguments": {"action": "list"}},
            ToolContext(session_id="cli:notes", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:apple-notes:platform_not_supported"

    asyncio.run(_scenario())


def test_run_skill_tmux_guide_mode_returns_structured_help(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "tmux",
        "name: tmux\ndescription: tmux helper\nscript: tmux",
    )

    async def _scenario() -> None:
        monkeypatch.setattr("clawlite.tools.skill.sys.platform", "linux")
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "tmux", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:tmux", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["platform"] == "linux|darwin"
        assert "capture" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_tmux_capture_dispatches_tmux_command(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "tmux",
        "name: tmux\ndescription: tmux helper\nscript: tmux",
    )

    async def _scenario() -> None:
        monkeypatch.setattr("clawlite.tools.skill.sys.platform", "linux")
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "tmux -S /tmp/clawlite.sock capture-pane -p -J -t clawlite-shell:0.0 -S -250": "exit=0\nstdout=pane\nstderr=",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "tmux",
                "tool_arguments": {
                    "action": "capture",
                    "socket": "/tmp/clawlite.sock",
                    "target": "clawlite-shell:0.0",
                    "lines": 250,
                },
            },
            ToolContext(session_id="cli:tmux", channel="cli", user_id="11"),
        )
        assert out == "exit=0\nstdout=pane\nstderr="

    asyncio.run(_scenario())


def test_run_skill_tmux_blocks_on_non_unix_platform(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "tmux",
        "name: tmux\ndescription: tmux helper\nscript: tmux",
    )

    async def _scenario() -> None:
        monkeypatch.setattr("clawlite.tools.skill.sys.platform", "win32")
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "tmux", "tool_arguments": {"action": "list_sessions"}},
            ToolContext(session_id="cli:tmux", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:tmux:platform_not_supported"

    asyncio.run(_scenario())


def test_run_skill_allows_execution_when_memory_policy_allows(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        memory = FakeMemory({"allowed": True})
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, memory=memory)
        out = await tool.run(
            {"name": "echo-skill", "input": "hello"},
            ToolContext(session_id="s8"),
        )
        assert out == "exec:echo hello::"
        assert memory.calls == [("skill", "s8")]

    asyncio.run(_scenario())


def test_run_skill_blocks_execution_when_memory_policy_denies(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        memory = FakeMemory({"allowed": False, "reason": "maintenance"})
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, memory=memory)
        out = await tool.run(
            {"name": "echo-skill", "input": "hello"},
            ToolContext(session_id="s9"),
        )
        assert out == "skill_blocked:echo-skill:memory_policy:maintenance"
        assert memory.calls == [("skill", "s9")]

    asyncio.run(_scenario())


def test_run_skill_blocks_execution_when_memory_policy_errors(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "echo-skill",
        "name: echo-skill\ndescription: echo\ncommand: echo",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeExecTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, memory=ExplodingMemory())
        out = await tool.run(
            {"name": "echo-skill", "input": "hello"},
            ToolContext(session_id="s10"),
        )
        assert out == "skill_blocked:echo-skill:memory_policy:policy_exception:runtimeerror"

    asyncio.run(_scenario())


def test_run_skill_github_precheck_blocks_when_auth_is_missing(tmp_path: Path, monkeypatch) -> None:
    _write_skill(
        tmp_path,
        "github",
        "name: github\ndescription: github\ncommand: gh issue",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        reg = ToolRegistry()
        reg.register(
            FakeExecStatusTool(
                {
                    "gh auth status": "exit=1\nstdout=\nstderr=not logged into any GitHub hosts",
                }
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "github", "args": ["list"]},
            ToolContext(session_id="cli:github", channel="cli", user_id="11"),
        )
        assert out == "skill_auth_required:github:gh:not logged into any GitHub hosts"

    asyncio.run(_scenario())


def test_run_skill_summarize_falls_back_to_provider_for_urls(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "summarize",
        "name: summarize\ndescription: summarize\nscript: summarize",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeWebFetchPayloadTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, provider=FakeProvider())
        out = await tool.run(
            {"name": "summarize", "input": "https://example.com"},
            ToolContext(session_id="cli:summarize", channel="cli", user_id="42"),
        )
        assert out.startswith("summary::Source: https://example.com")

    asyncio.run(_scenario())


def test_run_skill_summarize_blocks_when_web_fetch_is_unavailable(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "summarize",
        "name: summarize\ndescription: summarize\nscript: summarize",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, provider=FakeProvider())
        out = await tool.run(
            {"name": "summarize", "input": "https://example.com"},
            ToolContext(session_id="cli:summarize", channel="cli", user_id="42"),
        )
        assert out == "skill_blocked:summarize:summary_source_fetch_unavailable"

    asyncio.run(_scenario())


def test_run_skill_summarize_falls_back_to_provider_for_local_files(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "summarize",
        "name: summarize\ndescription: summarize\nscript: summarize",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeReadTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, provider=FakeProvider())
        out = await tool.run(
            {"name": "summarize", "input": "/tmp/demo.txt"},
            ToolContext(session_id="cli:summarize", channel="cli", user_id="42"),
        )
        assert out.startswith("summary::Source: /tmp/demo.txt")

    asyncio.run(_scenario())


def test_run_skill_summarize_blocks_when_reader_tools_are_unavailable(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "summarize",
        "name: summarize\ndescription: summarize\nscript: summarize",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg, provider=FakeProvider())
        out = await tool.run(
            {"name": "summarize", "input": "/tmp/demo.txt"},
            ToolContext(session_id="cli:summarize", channel="cli", user_id="42"),
        )
        assert out == "skill_blocked:summarize:summary_source_reader_unavailable"

    asyncio.run(_scenario())


def test_run_skill_weather_falls_back_to_open_meteo(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "weather",
        "name: weather\ndescription: weather\nscript: weather",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(
            FakeWebFetchSequenceTool(
                [
                    (
                        "https://wttr.in/Lisbon?format=3",
                        {
                            "ok": False,
                            "tool": "web_fetch",
                            "error": {"code": "http_error", "message": "status=503"},
                        },
                    ),
                    (
                        "https://geocoding-api.open-meteo.com/v1/search?name=Lisbon&count=1&language=en&format=json",
                        {
                            "ok": True,
                            "tool": "web_fetch",
                            "result": {
                                "text": json.dumps(
                                    {
                                        "results": [
                                            {
                                                "name": "Lisbon",
                                                "country": "Portugal",
                                                "latitude": 38.72,
                                                "longitude": -9.13,
                                            }
                                        ]
                                    }
                                )
                            },
                        },
                    ),
                    (
                        "https://api.open-meteo.com/v1/forecast?latitude=38.72&longitude=-9.13&current_weather=true&timezone=auto",
                        {
                            "ok": True,
                            "tool": "web_fetch",
                            "result": {
                                "text": json.dumps(
                                    {
                                        "current_weather": {
                                            "temperature": 19.5,
                                            "windspeed": 12.0,
                                            "weathercode": 2,
                                        }
                                    }
                                )
                            },
                        },
                    ),
                ]
            )
        )
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run({"name": "weather", "location": "Lisbon"}, ToolContext(session_id="cli:weather"))
        assert out == "Lisbon, Portugal: 19.5°C, partly cloudy, wind 12.0 km/h"

    asyncio.run(_scenario())


def test_run_skill_weather_blocks_when_web_fetch_is_unavailable(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "weather",
        "name: weather\ndescription: weather\nscript: weather",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run({"name": "weather", "location": "Lisbon"}, ToolContext(session_id="cli:weather"))
        assert out == "skill_blocked:weather:weather_fetch_unavailable"

    asyncio.run(_scenario())


def test_run_skill_weather_respects_web_fetch_channel_safety_policy(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "weather",
        "name: weather\ndescription: weather\nscript: weather",
    )

    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                risky_tools=["web_fetch"],
                blocked_channels=["telegram"],
                allowed_channels=[],
            )
        )
        reg.register(FakeWebFetchPayloadTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "weather", "location": "Lisbon"},
            ToolContext(session_id="telegram:weather", channel="telegram", user_id="42"),
        )
        assert out == "skill_blocked:weather:tool_blocked_by_safety_policy:web_fetch:telegram"

    asyncio.run(_scenario())


def test_run_skill_weather_reports_web_fetch_approval_requirement(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "weather",
        "name: weather\ndescription: weather\nscript: weather",
    )

    async def _scenario() -> None:
        reg = ToolRegistry(
            safety=ToolSafetyPolicyConfig(
                enabled=True,
                approval_specifiers=["web_fetch"],
                approval_channels=["telegram"],
                blocked_channels=[],
                allowed_channels=[],
            )
        )
        reg.register(FakeWebFetchPayloadTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "weather", "location": "Lisbon"},
            ToolContext(session_id="telegram:weather", channel="telegram", user_id="42"),
        )
        assert out == "skill_blocked:weather:tool_requires_approval:web_fetch:telegram"

    asyncio.run(_scenario())
def test_run_skill_coding_agent_wraps_sessions_spawn(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "coding-agent",
        "name: coding-agent\ndescription: coding\nscript: coding_agent",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        reg.register(FakeSessionsSpawnTool())
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "coding-agent",
                "tool_arguments": {"task": "Fix test suite", "share_scope": "family"},
            },
            ToolContext(session_id="cli:coding", channel="cli", user_id="7"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["task"] == "Fix test suite"
        assert payload["share_scope"] == "family"
        assert payload["session_id"] == "cli:coding"

    asyncio.run(_scenario())


def test_run_skill_healthcheck_returns_local_diagnostics_snapshot(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "healthcheck",
        "name: healthcheck\ndescription: health\nscript: healthcheck",
    )
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace_path": str(tmp_path / "workspace"),
                "state_path": str(tmp_path / "state"),
            }
        ),
        encoding="utf-8",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "healthcheck",
                "tool_arguments": {"config": str(config_path)},
            },
            ToolContext(session_id="cli:health", channel="cli", user_id="7"),
        )
        payload = json.loads(out)
        assert payload["workspace_path"] == str(tmp_path / "workspace")
        assert "validation" in payload
        assert "provider" in payload["validation"]
        assert "channels" in payload["validation"]

    asyncio.run(_scenario())


def test_run_skill_model_usage_executes_local_script_binding(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "model-usage",
        "name: model-usage\ndescription: usage\nscript: model_usage",
    )
    input_path = tmp_path / "usage.json"
    input_path.write_text(
        json.dumps(
            {
                "provider": "codex",
                "daily": [
                    {
                        "date": "2026-03-06",
                        "modelBreakdowns": [
                            {"modelName": "gpt-5-codex", "cost": 4.25},
                            {"modelName": "gpt-4.1-mini", "cost": 1.5},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "model-usage",
                "tool_arguments": {"provider": "codex", "mode": "all", "input": str(input_path)},
            },
            ToolContext(session_id="cli:model-usage"),
        )
        assert "Provider: codex" in out
        assert "gpt-5-codex" in out

    asyncio.run(_scenario())


def test_run_skill_session_logs_reads_jsonl_without_jq_or_rg(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "session-logs",
        "name: session-logs\ndescription: logs\nscript: session_logs",
    )
    state_path = tmp_path / "state"
    sessions_dir = state_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "workspace_path": str(tmp_path / "workspace"),
                "state_path": str(state_path),
            }
        ),
        encoding="utf-8",
    )
    (sessions_dir / "cli_history.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"session_id": "cli:history", "role": "user", "content": "deploy status", "ts": "2026-03-07T00:00:00Z", "metadata": {"channel": "telegram"}}),
                json.dumps({"session_id": "cli:history", "role": "assistant", "content": "deployment healthy", "ts": "2026-03-07T00:01:00Z", "metadata": {"channel": "telegram"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "session-logs",
                "tool_arguments": {"config": str(config_path), "session_id": "cli:history", "role": "assistant"},
            },
            ToolContext(session_id="cli:logs"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["session_id"] == "cli:history"
        assert payload["count"] == 1
        assert payload["messages"][0]["content"] == "deployment healthy"

    asyncio.run(_scenario())


def test_run_skill_notion_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "notion",
        "name: notion\ndescription: notion helper\nscript: notion",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "notion", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:notion", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert "usage" in payload
        assert payload["auth"]["required_env"] == ["NOTION_API_KEY"]
        assert len(payload["examples"]) >= 2
        assert "search" in payload["available_actions"]
        assert "request" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_notion_search_dispatches_request(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "notion",
        "name: notion\ndescription: notion helper\nscript: notion",
    )

    calls: list[dict[str, object]] = []

    async def _fake_notion_request(self, *, method, path, payload, timeout, token, notion_version, spec_name):
        del self, timeout
        calls.append(
            {
                "method": method,
                "path": path,
                "payload": payload,
                "token": token,
                "notion_version": notion_version,
                "spec_name": spec_name,
            }
        )
        return json.dumps({"ok": True, "results": []})

    async def _scenario() -> None:
        monkeypatch.setenv("NOTION_API_KEY", "notion-secret")
        monkeypatch.setattr(SkillTool, "_notion_request", _fake_notion_request)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "notion",
                "tool_arguments": {
                    "action": "search",
                    "query": "roadmap",
                },
            },
            ToolContext(session_id="cli:notion", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert calls == [
            {
                "method": "POST",
                "path": "/search",
                "payload": {"query": "roadmap"},
                "token": "notion-secret",
                "notion_version": "2022-06-28",
                "spec_name": "notion",
            }
        ]

    asyncio.run(_scenario())


def test_run_skill_notion_blocks_without_auth(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "notion",
        "name: notion\ndescription: notion helper\nscript: notion",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("NOTION_API_KEY", raising=False)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "notion",
                "tool_arguments": {
                    "action": "search",
                    "query": "roadmap",
                },
            },
            ToolContext(session_id="cli:notion", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:notion:notion_auth_missing"

    asyncio.run(_scenario())


def test_run_skill_jira_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "jira",
        "name: jira\ndescription: jira helper\nscript: jira",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "jira", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:jira", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert "usage" in payload
        assert "JIRA_BASE_URL" in payload["auth"]["required_env"]
        assert len(payload["examples"]) >= 2
        assert "issue_get" in payload["available_actions"]
        assert "request" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_jira_search_dispatches_request(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "jira",
        "name: jira\ndescription: jira helper\nscript: jira",
    )

    calls: list[dict[str, object]] = []

    async def _fake_jira_request(self, *, method, base_url, email, token, path, payload, timeout, spec_name):
        del self, timeout
        calls.append(
            {
                "method": method,
                "base_url": base_url,
                "email": email,
                "token": token,
                "path": path,
                "payload": payload,
                "spec_name": spec_name,
            }
        )
        return json.dumps({"ok": True, "issues": []})

    async def _scenario() -> None:
        monkeypatch.setenv("JIRA_BASE_URL", "https://acme.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "jira-secret")
        monkeypatch.setattr(SkillTool, "_jira_request", _fake_jira_request)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "jira",
                "tool_arguments": {
                    "action": "search",
                    "jql": "project = CORE",
                    "max_results": 15,
                },
            },
            ToolContext(session_id="cli:jira", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert calls == [
            {
                "method": "GET",
                "base_url": "https://acme.atlassian.net",
                "email": "bot@example.com",
                "token": "jira-secret",
                "path": "/search",
                "payload": {"jql": "project = CORE", "maxResults": 15},
                "spec_name": "jira",
            }
        ]

    asyncio.run(_scenario())


def test_run_skill_jira_blocks_without_auth(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "jira",
        "name: jira\ndescription: jira helper\nscript: jira",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.delenv("JIRA_EMAIL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "jira",
                "tool_arguments": {
                    "action": "search",
                    "jql": "project = CORE",
                },
            },
            ToolContext(session_id="cli:jira", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:jira:jira_auth_missing"

    asyncio.run(_scenario())


def test_run_skill_linear_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "linear",
        "name: linear\ndescription: linear helper\nscript: linear",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "linear", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:linear", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert "usage" in payload
        assert payload["auth"]["required_env"] == ["LINEAR_API_KEY"]
        assert len(payload["examples"]) >= 2
        assert "issues_list" in payload["available_actions"]
        assert "request" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_linear_request_dispatches_graphql(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "linear",
        "name: linear\ndescription: linear helper\nscript: linear",
    )

    calls: list[dict[str, object]] = []

    async def _fake_linear_request(self, *, endpoint, token, query, variables, timeout, spec_name):
        del self, timeout
        calls.append(
            {
                "endpoint": endpoint,
                "token": token,
                "query": query,
                "variables": variables,
                "spec_name": spec_name,
            }
        )
        return json.dumps({"data": {"viewer": {"id": "u1"}}})

    async def _scenario() -> None:
        monkeypatch.setenv("LINEAR_API_KEY", "linear-secret")
        monkeypatch.setattr(SkillTool, "_linear_request", _fake_linear_request)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "linear",
                "tool_arguments": {
                    "action": "request",
                    "query": "query { viewer { id } }",
                    "variables": {"team": "core"},
                },
            },
            ToolContext(session_id="cli:linear", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["data"]["viewer"]["id"] == "u1"
        assert calls == [
            {
                "endpoint": "https://api.linear.app/graphql",
                "token": "linear-secret",
                "query": "query { viewer { id } }",
                "variables": {"team": "core"},
                "spec_name": "linear",
            }
        ]

    asyncio.run(_scenario())


def test_run_skill_linear_blocks_without_auth(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "linear",
        "name: linear\ndescription: linear helper\nscript: linear",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "linear",
                "tool_arguments": {
                    "action": "issues_list",
                },
            },
            ToolContext(session_id="cli:linear", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:linear:linear_auth_missing"

    asyncio.run(_scenario())


def test_run_skill_trello_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "trello",
        "name: trello\ndescription: trello helper\nscript: trello",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "trello", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:trello", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert "usage" in payload
        assert "TRELLO_API_KEY" in payload["auth"]["required_env"]
        assert len(payload["examples"]) >= 2
        assert "boards_list" in payload["available_actions"]
        assert "request" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_trello_boards_list_dispatches_request(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "trello",
        "name: trello\ndescription: trello helper\nscript: trello",
    )

    calls: list[dict[str, object]] = []

    async def _fake_trello_request(self, *, method, base_url, api_key, token, path, payload, timeout, spec_name):
        del self, timeout
        calls.append(
            {
                "method": method,
                "base_url": base_url,
                "api_key": api_key,
                "token": token,
                "path": path,
                "payload": payload,
                "spec_name": spec_name,
            }
        )
        return json.dumps({"ok": True, "boards": []})

    async def _scenario() -> None:
        monkeypatch.setenv("TRELLO_API_KEY", "trello-key")
        monkeypatch.setenv("TRELLO_TOKEN", "trello-token")
        monkeypatch.setattr(SkillTool, "_trello_request", _fake_trello_request)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "trello",
                "tool_arguments": {
                    "action": "boards_list",
                    "fields": "id,name",
                },
            },
            ToolContext(session_id="cli:trello", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["ok"] is True
        assert calls == [
            {
                "method": "GET",
                "base_url": "https://api.trello.com/1",
                "api_key": "trello-key",
                "token": "trello-token",
                "path": "/members/me/boards",
                "payload": {"fields": "id,name"},
                "spec_name": "trello",
            }
        ]

    asyncio.run(_scenario())


def test_run_skill_trello_blocks_without_auth(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "trello",
        "name: trello\ndescription: trello helper\nscript: trello",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("TRELLO_API_KEY", raising=False)
        monkeypatch.delenv("TRELLO_TOKEN", raising=False)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "trello",
                "tool_arguments": {
                    "action": "boards_list",
                },
            },
            ToolContext(session_id="cli:trello", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:trello:trello_auth_missing"

    asyncio.run(_scenario())


def test_run_skill_spotify_guide_mode_returns_structured_help(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "spotify",
        "name: spotify\ndescription: spotify helper\nscript: spotify",
    )

    async def _scenario() -> None:
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {"name": "spotify", "tool_arguments": {"action": "guide"}},
            ToolContext(session_id="cli:spotify", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["mode"] == "guide"
        assert "usage" in payload
        assert "SPOTIFY_CLIENT_ID" in payload["auth"]["required_env"]
        assert "SPOTIFY_ACCESS_TOKEN" in payload["auth"]["optional_env"]
        assert len(payload["examples"]) >= 2
        assert "search" in payload["available_actions"]
        assert "request" in payload["available_actions"]

    asyncio.run(_scenario())


def test_run_skill_spotify_search_dispatches_request(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "spotify",
        "name: spotify\ndescription: spotify helper\nscript: spotify",
    )

    calls: list[dict[str, object]] = []

    async def _fake_spotify_request(self, *, method, token, path, params, payload, timeout, spec_name):
        del self, timeout
        calls.append(
            {
                "method": method,
                "token": token,
                "path": path,
                "params": params,
                "payload": payload,
                "spec_name": spec_name,
            }
        )
        return json.dumps({"tracks": {"items": []}})

    async def _scenario() -> None:
        monkeypatch.setenv("SPOTIFY_ACCESS_TOKEN", "spotify-access")
        monkeypatch.setattr(SkillTool, "_spotify_request", _fake_spotify_request)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "spotify",
                "tool_arguments": {
                    "action": "search",
                    "query": "radiohead",
                    "type": "track",
                    "limit": 5,
                },
            },
            ToolContext(session_id="cli:spotify", channel="cli", user_id="11"),
        )
        payload = json.loads(out)
        assert "tracks" in payload
        assert calls == [
            {
                "method": "GET",
                "token": "spotify-access",
                "path": "/search",
                "params": {"q": "radiohead", "type": "track", "limit": 5},
                "payload": {},
                "spec_name": "spotify",
            }
        ]

    asyncio.run(_scenario())


def test_run_skill_spotify_blocks_without_auth(monkeypatch, tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        "spotify",
        "name: spotify\ndescription: spotify helper\nscript: spotify",
    )

    async def _scenario() -> None:
        monkeypatch.delenv("SPOTIFY_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
        monkeypatch.delenv("SPOTIFY_CLIENT_SECRET", raising=False)
        reg = ToolRegistry()
        tool = SkillTool(loader=SkillsLoader(builtin_root=tmp_path), registry=reg)
        out = await tool.run(
            {
                "name": "spotify",
                "tool_arguments": {
                    "action": "search",
                    "query": "radiohead",
                },
            },
            ToolContext(session_id="cli:spotify", channel="cli", user_id="11"),
        )
        assert out == "skill_blocked:spotify:spotify_auth_missing"

    asyncio.run(_scenario())

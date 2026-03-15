"""Tests for SubagentManager parent/child context propagation."""
from __future__ import annotations

import asyncio
import pytest


@pytest.mark.asyncio
async def test_subagent_spawn_with_parent_session():
    from clawlite.core.subagent import SubagentManager

    mgr = SubagentManager()
    results = []

    async def runner(session_id: str, task: str) -> str:
        results.append(f"ran:{session_id}")
        return "child_result"

    run = await mgr.spawn(
        session_id="child_session",
        task="do something",
        runner=runner,
        parent_session_id="parent_session",
    )
    await asyncio.sleep(0.2)

    assert run.status == "done"
    assert run.result == "child_result"
    # child session_id should be prefixed with parent
    assert run.session_id.startswith("parent_session:sub:")
    # parent_session_id stored in metadata
    assert run.metadata.get("parent_session_id") == "parent_session"


@pytest.mark.asyncio
async def test_subagent_spawn_without_parent_unchanged():
    from clawlite.core.subagent import SubagentManager

    mgr = SubagentManager()

    async def runner(sid: str, task: str) -> str:
        return "ok"

    run = await mgr.spawn(session_id="s1", task="task", runner=runner)
    await asyncio.sleep(0.2)
    assert run.status == "done"
    assert run.session_id == "s1"
    assert "parent_session_id" not in run.metadata


@pytest.mark.asyncio
async def test_child_session_id_unique_per_spawn():
    from clawlite.core.subagent import SubagentManager

    mgr = SubagentManager(max_concurrent_runs=4, per_session_quota=10)
    session_ids = []

    async def runner(sid: str, task: str) -> str:
        session_ids.append(sid)
        return "ok"

    run1 = await mgr.spawn(session_id="child", task="task1", runner=runner, parent_session_id="parent")
    run2 = await mgr.spawn(session_id="child", task="task2", runner=runner, parent_session_id="parent")

    await asyncio.sleep(0.3)
    # Both children derived from parent but with unique run_id suffix
    assert run1.session_id != run2.session_id
    assert run1.session_id.startswith("parent:sub:")
    assert run2.session_id.startswith("parent:sub:")

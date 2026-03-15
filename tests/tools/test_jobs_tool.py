"""Tests for JobsTool — agent interface to the job queue."""
from __future__ import annotations

import json
import asyncio
import pytest


@pytest.fixture
def jobs_queue():
    from clawlite.jobs.queue import JobQueue
    return JobQueue(concurrency=1)


@pytest.fixture
def tool_and_queue(jobs_queue):
    from clawlite.tools.jobs import JobsTool
    from clawlite.tools.base import ToolContext
    return JobsTool(queue=jobs_queue), jobs_queue


@pytest.mark.asyncio
async def test_submit_job_via_tool(tool_and_queue):
    t, q = tool_and_queue
    from clawlite.tools.base import ToolContext
    ctx = ToolContext(session_id="s1", channel="cli", user_id="u1")

    result = await t.run({"action": "submit", "kind": "agent_run", "payload": {"msg": "hi"}}, ctx)
    data = json.loads(result)
    assert data["ok"] is True
    assert "job_id" in data
    assert len(q.list_jobs()) == 1


@pytest.mark.asyncio
async def test_status_job_via_tool(tool_and_queue):
    t, q = tool_and_queue
    from clawlite.tools.base import ToolContext
    ctx = ToolContext(session_id="s1", channel="cli", user_id="u1")

    job = q.submit("agent_run", {"x": 1}, session_id="s1")
    result = await t.run({"action": "status", "job_id": job.id}, ctx)
    data = json.loads(result)
    assert data["job_id"] == job.id
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_list_jobs_via_tool(tool_and_queue):
    t, q = tool_and_queue
    from clawlite.tools.base import ToolContext
    ctx = ToolContext(session_id="s1", channel="cli", user_id="u1")

    q.submit("agent_run", {}, session_id="s1")
    q.submit("agent_run", {}, session_id="s1")
    result = await t.run({"action": "list"}, ctx)
    data = json.loads(result)
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_cancel_job_via_tool(tool_and_queue):
    t, q = tool_and_queue
    from clawlite.tools.base import ToolContext
    ctx = ToolContext(session_id="s1", channel="cli", user_id="u1")

    job = q.submit("agent_run", {}, session_id="s1")
    result = await t.run({"action": "cancel", "job_id": job.id}, ctx)
    data = json.loads(result)
    assert data["ok"] is True
    assert q.status(job.id).status == "cancelled"


@pytest.mark.asyncio
async def test_status_unknown_job(tool_and_queue):
    t, q = tool_and_queue
    from clawlite.tools.base import ToolContext
    ctx = ToolContext(session_id="s1", channel="cli", user_id="u1")

    result = await t.run({"action": "status", "job_id": "nonexistent"}, ctx)
    assert "error" in result.lower() or "not found" in result.lower()

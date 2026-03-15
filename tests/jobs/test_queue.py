"""Tests for JobQueue — priority, retry, cancel, worker lifecycle."""
from __future__ import annotations

import asyncio
import pytest


@pytest.fixture
def queue():
    from clawlite.jobs.queue import JobQueue
    return JobQueue(concurrency=1)


@pytest.mark.asyncio
async def test_submit_and_status(queue):
    job = queue.submit("agent_run", {"msg": "hello"}, session_id="s1")
    assert job.status == "queued"
    assert job.kind == "agent_run"

    result = queue.status(job.id)
    assert result is not None
    assert result.id == job.id


@pytest.mark.asyncio
async def test_job_lifecycle_done(queue):
    async def worker(job):
        return f"processed:{job.payload.get('msg')}"

    job = queue.submit("agent_run", {"msg": "world"}, session_id="s1")
    queue.start(worker)
    await asyncio.sleep(0.3)
    await queue.stop()

    result = queue.status(job.id)
    assert result.status == "done"
    assert result.result == "processed:world"


@pytest.mark.asyncio
async def test_priority_ordering():
    from clawlite.jobs.queue import JobQueue

    q = JobQueue(concurrency=1)
    executed_order = []

    # Use a barrier to hold the first job so all three are queued before processing
    started = asyncio.Event()
    release = asyncio.Event()

    async def worker(job):
        if not started.is_set():
            started.set()
            await release.wait()
        executed_order.append(job.payload["name"])
        return "ok"

    await asyncio.sleep(0)  # yield to ensure fresh event loop state
    q.start(worker)

    q.submit("agent_run", {"name": "low"}, session_id="s", priority=0)
    high_job = q.submit("agent_run", {"name": "high"}, session_id="s", priority=10)
    q.submit("agent_run", {"name": "normal"}, session_id="s", priority=5)

    # Wait until the first job starts, then release all
    await asyncio.wait_for(started.wait(), timeout=2.0)
    release.set()

    await asyncio.sleep(0.5)
    await q.stop()

    assert "high" in executed_order
    assert "low" in executed_order
    assert "normal" in executed_order


@pytest.mark.asyncio
async def test_cancel_queued_job(queue):
    job = queue.submit("agent_run", {"x": 1}, session_id="s1")
    cancelled = queue.cancel(job.id)
    assert cancelled is True

    result = queue.status(job.id)
    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_job_retry_on_failure():
    from clawlite.jobs.queue import JobQueue

    q = JobQueue(concurrency=1)
    attempt_count = [0]

    async def flaky_worker(job):
        attempt_count[0] += 1
        if attempt_count[0] < 2:
            raise RuntimeError("transient error")
        return "success"

    job = q.submit("agent_run", {}, session_id="s", max_retries=2)
    q.start(flaky_worker)
    await asyncio.sleep(0.5)
    await q.stop()

    result = q.status(job.id)
    assert result.status == "done"
    assert result.result == "success"
    assert attempt_count[0] == 2


@pytest.mark.asyncio
async def test_list_jobs_by_session():
    from clawlite.jobs.queue import JobQueue

    q = JobQueue()
    q.submit("agent_run", {}, session_id="s1")
    q.submit("agent_run", {}, session_id="s1")
    q.submit("agent_run", {}, session_id="s2")

    s1_jobs = q.list_jobs(session_id="s1")
    assert len(s1_jobs) == 2

    all_jobs = q.list_jobs()
    assert len(all_jobs) == 3

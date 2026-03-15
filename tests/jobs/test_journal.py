"""Tests for JobJournal SQLite persistence."""
from __future__ import annotations

import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def journal_path(tmp_path):
    return tmp_path / "test_jobs.db"


@pytest.fixture
def journal(journal_path):
    from clawlite.jobs.journal import JobJournal
    j = JobJournal(journal_path)
    j.open()
    yield j
    j.close()


def _make_job(kind: str = "agent_run", status: str = "queued"):
    from clawlite.jobs.queue import Job
    return Job(id="abc123", kind=kind, payload={"x": 1}, priority=5, session_id="s1", status=status)


def test_save_and_load_queued(journal):
    job = _make_job()
    journal.save(job)
    rows = journal.load_queued()
    assert len(rows) == 1
    assert rows[0].id == "abc123"
    assert rows[0].status == "queued"


def test_save_update_status(journal):
    job = _make_job()
    journal.save(job)
    job.status = "done"
    job.result = "all good"
    journal.save(job)

    rows = journal.load_queued()
    assert len(rows) == 0  # no more queued

    all_rows = journal.load_all()
    assert len(all_rows) == 1
    assert all_rows[0].status == "done"
    assert all_rows[0].result == "all good"


def test_load_queued_skips_non_queued(journal):
    job1 = _make_job()
    job1.id = "j1"
    job2 = _make_job(status="done")
    job2.id = "j2"
    journal.save(job1)
    journal.save(job2)

    queued = journal.load_queued()
    assert len(queued) == 1
    assert queued[0].id == "j1"


def test_restart_recovery(journal_path):
    """Simulates restart by creating new journal instance from same path."""
    from clawlite.jobs.journal import JobJournal
    from clawlite.jobs.queue import Job

    j1 = JobJournal(journal_path)
    j1.open()
    job = Job(id="persist1", kind="agent_run", payload={}, priority=5, session_id="s")
    j1.save(job)
    j1.close()

    j2 = JobJournal(journal_path)
    j2.open()
    rows = j2.load_queued()
    j2.close()

    assert len(rows) == 1
    assert rows[0].id == "persist1"

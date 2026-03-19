"""Tests for the Valkyrie session reaper."""
from __future__ import annotations

import asyncio
import pytest

from clawlite.runtime.valkyrie import ValkyrieReaper


def _make_store(sessions: list[dict]) -> object:
    class FakeStore:
        def __init__(self):
            self.archived: list[str] = []
            self.purged: list[str] = []
            self._sessions = sessions

        def list_sessions(self):
            return list(self._sessions)

        def archive_session(self, sid: str):
            self.archived.append(sid)

        def purge_session(self, sid: str):
            self.purged.append(sid)

    return FakeStore()


# ── Classification ─────────────────────────────────────────────────────────────

def test_fresh_session_skipped():
    v = ValkyrieReaper(idle_days=7, dead_days=30)
    sess = {"session_id": "s1", "status": "active", "last_active_at": "2099-01-01T00:00:00+00:00"}
    assert v._classify(sess) == "skip"


def test_idle_session_archived():
    # 2020-01-01 is ~2270 days ago; idle=1000d, dead=3000d → in archive window
    v = ValkyrieReaper(idle_days=1000, dead_days=3000)
    sess = {"session_id": "s1", "status": "active", "last_active_at": "2020-01-01T00:00:00+00:00"}
    assert v._classify(sess) == "archive"


def test_very_old_session_purged():
    # 2020-01-01 is ~2270 days ago; idle=7d, dead=14d → way past dead threshold
    v = ValkyrieReaper(idle_days=7, dead_days=14)
    sess = {"session_id": "s1", "status": "active", "last_active_at": "2020-01-01T00:00:00+00:00"}
    assert v._classify(sess) == "purge"


def test_purged_session_skipped():
    v = ValkyrieReaper(idle_days=7, dead_days=30)
    sess = {"session_id": "s1", "status": "purged", "last_active_at": "2018-01-01T00:00:00+00:00"}
    assert v._classify(sess) == "skip"


def test_archived_session_purged_after_dead_window():
    v = ValkyrieReaper(idle_days=7, dead_days=30)
    sess = {
        "session_id": "s1",
        "status": "archived",
        "last_active_at": "2018-01-01T00:00:00+00:00",
        "archived_at": "2018-01-08T00:00:00+00:00",
    }
    assert v._classify(sess) == "purge"


# ── reap_once ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reap_once_archives_idle_sessions():
    # 2020 dates are ~2270 days ago; idle=1000d, dead=3000d → archive window
    sessions = [
        {"session_id": "old1", "status": "active", "last_active_at": "2020-01-01T00:00:00+00:00"},
        {"session_id": "old2", "status": "active", "last_active_at": "2020-06-01T00:00:00+00:00"},
        {"session_id": "new1", "status": "active", "last_active_at": "2099-01-01T00:00:00+00:00"},
    ]
    store = _make_store(sessions)
    v = ValkyrieReaper(idle_days=1000, dead_days=3000)
    v._session_store = store
    summary = await v.reap_once()
    assert summary["archived"] == 2
    assert summary["skipped"] == 1
    assert "old1" in store.archived
    assert "old2" in store.archived


@pytest.mark.asyncio
async def test_reap_once_purges_very_old():
    sessions = [
        {"session_id": "ancient", "status": "active", "last_active_at": "2010-01-01T00:00:00+00:00"},
    ]
    store = _make_store(sessions)
    v = ValkyrieReaper(idle_days=7, dead_days=14)
    v._session_store = store
    summary = await v.reap_once()
    assert summary["purged"] == 1
    assert "ancient" in store.purged


@pytest.mark.asyncio
async def test_reap_once_empty_store():
    store = _make_store([])
    v = ValkyrieReaper()
    v._session_store = store
    summary = await v.reap_once()
    assert summary["total"] == 0
    assert summary["archived"] == 0
    assert summary["purged"] == 0


@pytest.mark.asyncio
async def test_reap_once_increments_stats():
    sessions = [
        {"session_id": "s1", "status": "active", "last_active_at": "2020-01-01T00:00:00+00:00"},
    ]
    store = _make_store(sessions)
    v = ValkyrieReaper(idle_days=1000, dead_days=3000)
    v._session_store = store
    await v.reap_once()
    assert v._sweeps == 1
    assert v._total_archived == 1


# ── status ─────────────────────────────────────────────────────────────────────

def test_status_fields():
    v = ValkyrieReaper()
    s = v.status()
    assert "running" in s
    assert "sweeps" in s
    assert "total_archived" in s
    assert "total_purged" in s

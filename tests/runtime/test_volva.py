"""Tests for the Völva background memory oracle."""
from __future__ import annotations

import asyncio
import pytest

from clawlite.runtime.volva import VolvaOracle


def _make_memory(categories: dict) -> object:
    """Build a fake memory store with list_categories()."""
    class FakeMemory:
        def __init__(self):
            self.purged: list[str] = []
            self._cats = categories

        def list_categories(self):
            return [
                {"category": cat, **info}
                for cat, info in self._cats.items()
            ]

        async def purge_decayed(self, *, category: str) -> int:
            self.purged.append(category)
            return 1

    return FakeMemory()


def _make_consolidator() -> object:
    class FakeConsolidator:
        def __init__(self):
            self.consolidated: list[str] = []

        async def consolidate(self, records, *, category: str) -> str | None:
            self.consolidated.append(category)
            return "summary"

    return FakeConsolidator()


# ── _identify_targets ──────────────────────────────────────────────────────────

def test_identify_stale_from_muninn():
    v = VolvaOracle(stale_hours=48.0, consolidation_threshold=50)
    snapshot = {
        "ravens_counsel": {
            "muninn": {
                "stale_categories": ["context", "session"],
                "consolidation_needed": False,
            }
        }
    }
    stale, oversize = v._identify_targets(snapshot)
    assert "context" in stale
    assert "session" in stale
    assert not oversize


def test_identify_oversize_from_muninn_and_meta():
    v = VolvaOracle(stale_hours=48.0, consolidation_threshold=50)
    snapshot = {
        "ravens_counsel": {
            "muninn": {
                "stale_categories": [],
                "consolidation_needed": True,
            }
        },
        "memory": {
            "facts": {"count": 80, "updated_at": "2025-01-01T00:00:00+00:00"},
        }
    }
    stale, oversize = v._identify_targets(snapshot)
    assert "facts" in oversize


def test_identify_falls_back_to_memory_store():
    v = VolvaOracle(stale_hours=1.0, consolidation_threshold=50)
    mem = _make_memory({
        "context": {"count": 5, "updated_at": "2020-01-01T00:00:00+00:00"},
        "fresh": {"count": 3, "updated_at": "2099-01-01T00:00:00+00:00"},
    })
    v._memory = mem
    stale, oversize = v._identify_targets({})
    assert "context" in stale
    assert "fresh" not in stale


def test_identify_no_targets_empty_snapshot():
    v = VolvaOracle()
    stale, oversize = v._identify_targets({})
    assert stale == []
    assert oversize == []


# ── _tick ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tick_prunes_stale_category():
    v = VolvaOracle(stale_hours=48.0)
    mem = _make_memory({})
    consolidator = _make_consolidator()
    v._memory = mem
    v._consolidator = consolidator
    snapshot = {
        "ravens_counsel": {
            "muninn": {"stale_categories": ["session"], "consolidation_needed": False}
        }
    }
    await v._tick(snapshot)
    assert v._ticks == 1
    assert "session" in mem.purged


@pytest.mark.asyncio
async def test_tick_consolidates_oversize_category():
    v = VolvaOracle(consolidation_threshold=50)
    mem = _make_memory({"facts": {"count": 80, "updated_at": "2025-01-01T00:00:00+00:00"}})

    # Make _fetch_category_records return something
    def fake_recall(cat, limit=100):
        return [object()] * 10

    mem.recall = fake_recall  # type: ignore[attr-defined]
    consolidator = _make_consolidator()
    v._memory = mem
    v._consolidator = consolidator

    snapshot = {
        "ravens_counsel": {
            "muninn": {"stale_categories": [], "consolidation_needed": True}
        },
        "memory": {"facts": {"count": 80, "updated_at": "2025-01-01T00:00:00+00:00"}}
    }
    await v._tick(snapshot)
    assert "facts" in consolidator.consolidated


@pytest.mark.asyncio
async def test_tick_no_targets_logs_healthy():
    v = VolvaOracle()
    v._memory = _make_memory({})
    v._consolidator = _make_consolidator()
    await v._tick({})  # should not raise; nothing to tend


# ── status ─────────────────────────────────────────────────────────────────────

def test_status_fields():
    v = VolvaOracle()
    s = v.status()
    assert "running" in s
    assert "ticks" in s
    assert "categories_consolidated" in s
    assert "categories_pruned" in s
    assert "last_error" in s


# ── max_categories_per_tick ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_max_categories_per_tick_respected():
    v = VolvaOracle(max_categories_per_tick=1)
    mem = _make_memory({})

    async def fake_purge(*, category: str) -> int:
        mem.purged.append(category)
        return 1

    mem.purge_decayed = fake_purge  # type: ignore[attr-defined]
    v._memory = mem
    v._consolidator = _make_consolidator()

    snapshot = {
        "ravens_counsel": {
            "muninn": {
                "stale_categories": ["a", "b", "c"],
                "consolidation_needed": False,
            }
        }
    }
    await v._tick(snapshot)
    # Only 1 category should have been tended despite 3 stale
    assert len(mem.purged) <= 1

"""Tests for the Huginn & Muninn dual-raven autonomy analysis."""
from __future__ import annotations

import asyncio
import pytest

from clawlite.core.huginn_muninn import (
    HuginnInsight,
    MuninnInsight,
    RavensCounsel,
    ravens_consult,
    wrap_with_ravens,
)


# ── Huginn ─────────────────────────────────────────────────────────────────────

def test_huginn_clean_snapshot_returns_none_priority():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync
    insight = _huginn_analyze_sync({})
    assert insight.priority in ("none", "low")
    assert isinstance(insight.attention_items, list)


def test_huginn_detects_component_down():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync
    snapshot = {"health": {"workers": {"running": False, "last_error": "connection_refused"}}}
    insight = _huginn_analyze_sync(snapshot)
    assert insight.priority == "high"
    assert insight.health_warnings


def test_huginn_detects_high_failure_rate():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync
    snapshot = {"workers": {"total": 100, "failed": 40, "done": 60}}
    insight = _huginn_analyze_sync(snapshot)
    assert insight.error_trend == "rising"
    assert insight.priority in ("high", "medium")


def test_huginn_falling_error_trend():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync
    snapshot = {"workers": {"total": 200, "failed": 5, "done": 195}}
    insight = _huginn_analyze_sync(snapshot)
    assert insight.error_trend == "falling"


def test_huginn_stalled_sessions_detected():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync
    # last_active_at well in the past
    snapshot = {"sessions": {
        "sess_abc": {"last_active_at": "2020-01-01T00:00:00+00:00"},
        "sess_xyz": {"last_active_at": "2020-06-01T00:00:00+00:00"},
    }}
    insight = _huginn_analyze_sync(snapshot)
    assert len(insight.stalled_sessions) == 2


def test_huginn_insight_to_dict():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync
    insight = _huginn_analyze_sync({})
    d = insight.to_dict()
    assert d["raven"] == "huginn"
    assert "priority" in d
    assert "suggested_action" in d


# ── Muninn ─────────────────────────────────────────────────────────────────────

def test_muninn_empty_snapshot():
    from clawlite.core.huginn_muninn import _muninn_analyze_sync
    insight = _muninn_analyze_sync({})
    assert insight.total_memory_items == 0
    assert not insight.consolidation_needed
    assert not insight.stale_categories


def test_muninn_detects_stale_category():
    from clawlite.core.huginn_muninn import _muninn_analyze_sync
    snapshot = {"memory": {
        "context": {"count": 5, "updated_at": "2020-01-01T00:00:00+00:00"},
    }}
    insight = _muninn_analyze_sync(snapshot)
    assert "context" in insight.stale_categories


def test_muninn_detects_oversize():
    from clawlite.core.huginn_muninn import _muninn_analyze_sync, _CONSOLIDATION_ITEM_THRESHOLD
    snapshot = {"memory": {
        "facts": {"count": _CONSOLIDATION_ITEM_THRESHOLD + 10, "updated_at": "2025-01-01T00:00:00+00:00"},
    }}
    insight = _muninn_analyze_sync(snapshot)
    assert insight.consolidation_needed


def test_muninn_top_categories_sorted():
    from clawlite.core.huginn_muninn import _muninn_analyze_sync
    snapshot = {"memory": {
        "a": {"count": 1, "updated_at": "2025-01-01T00:00:00+00:00"},
        "b": {"count": 10, "updated_at": "2025-01-01T00:00:00+00:00"},
        "c": {"count": 5, "updated_at": "2025-01-01T00:00:00+00:00"},
    }}
    insight = _muninn_analyze_sync(snapshot)
    assert insight.top_categories[0] == "b"


def test_muninn_insight_to_dict():
    from clawlite.core.huginn_muninn import _muninn_analyze_sync
    insight = _muninn_analyze_sync({})
    d = insight.to_dict()
    assert d["raven"] == "muninn"
    assert "stale_categories" in d
    assert "consolidation_needed" in d


# ── RavensCounsel ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ravens_consult_returns_counsel():
    counsel = await ravens_consult({})
    assert isinstance(counsel.huginn, HuginnInsight)
    assert isinstance(counsel.muninn, MuninnInsight)
    assert isinstance(counsel.consulted_at, str)


@pytest.mark.asyncio
async def test_ravens_consult_combined_priority_high():
    snapshot = {
        "health": {"db": {"running": False}},
        "memory": {"context": {"count": 5, "updated_at": "2020-01-01T00:00:00+00:00"}},
    }
    counsel = await ravens_consult(snapshot)
    assert counsel.combined_priority in ("high", "medium")


def test_counsel_to_dict():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync, _muninn_analyze_sync
    counsel = RavensCounsel(
        huginn=_huginn_analyze_sync({}),
        muninn=_muninn_analyze_sync({}),
    )
    d = counsel.to_dict()
    assert "huginn" in d
    assert "muninn" in d
    assert "combined_priority" in d


def test_counsel_summary_lines():
    from clawlite.core.huginn_muninn import _huginn_analyze_sync, _muninn_analyze_sync
    counsel = RavensCounsel(
        huginn=_huginn_analyze_sync({}),
        muninn=_muninn_analyze_sync({}),
    )
    lines = counsel.summary_lines()
    assert any("Huginn" in l for l in lines)
    assert any("Muninn" in l for l in lines)


# ── wrap_with_ravens ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wrap_with_ravens_enriches_snapshot():
    received_snapshots = []

    async def fake_callback(snapshot):
        received_snapshots.append(snapshot)
        return "ok"

    wrapped = wrap_with_ravens(fake_callback)
    await wrapped({})
    assert received_snapshots
    assert "ravens_counsel" in received_snapshots[0]


@pytest.mark.asyncio
async def test_wrap_with_ravens_tolerates_error():
    """Ravens should never block the callback even if analysis fails."""
    async def bad_ravens_callback(snapshot):
        return "called"

    # Patch ravens_consult to raise
    import clawlite.core.huginn_muninn as hm
    original = hm.ravens_consult
    async def broken(*a, **kw):
        raise RuntimeError("raven fell")
    hm.ravens_consult = broken

    try:
        wrapped = wrap_with_ravens(bad_ravens_callback)
        result = await wrapped({})
        assert result == "called"
    finally:
        hm.ravens_consult = original

"""Tests for the Norns three-phase autonomy prompt structure."""
from __future__ import annotations

import pytest

from clawlite.core.norns import NornsFrame, weave, norns_prompt, norns_autonomy_prompt


# ── weave ──────────────────────────────────────────────────────────────────────

def test_weave_empty_snapshot():
    frame = weave({})
    assert isinstance(frame.urd, dict)
    assert isinstance(frame.verdandi, dict)
    assert isinstance(frame.skuld, dict)


def test_weave_autonomy_history_goes_to_urd():
    snapshot = {
        "autonomy": {
            "last_run_at": "2025-01-01T10:00:00+00:00",
            "last_result_excerpt": "AUTONOMY_IDLE",
            "ticks": 42,
            "run_success": 40,
            "run_failures": 2,
        }
    }
    frame = weave(snapshot)
    assert frame.urd.get("last_autonomy_run") == "2025-01-01T10:00:00+00:00"
    assert frame.urd.get("total_ticks") == 42
    assert "run_failures" in frame.urd


def test_weave_health_goes_to_verdandi():
    snapshot = {"health": {"workers": {"running": True}, "db": {"running": False}}}
    frame = weave(snapshot)
    assert "component_health" in frame.verdandi
    assert frame.verdandi["component_health"]["db"] is False


def test_weave_stale_memory_goes_to_skuld():
    snapshot = {
        "ravens_counsel": {
            "huginn": {"priority": "low", "attention_items": [], "health_warnings": [],
                       "error_trend": "stable", "suggested_action": ""},
            "muninn": {"stale_categories": ["context", "session"], "consolidation_needed": False},
        }
    }
    frame = weave(snapshot)
    assert "stale_memory_realms" in frame.skuld
    assert "context" in frame.skuld["stale_memory_realms"]


def test_weave_huginn_high_priority_in_skuld():
    snapshot = {
        "ravens_counsel": {
            "huginn": {
                "priority": "high",
                "suggested_action": "Fix the database",
                "attention_items": ["DB down"],
                "health_warnings": ["db: not running"],
                "error_trend": "rising",
                "stalled_sessions": [],
            },
            "muninn": {"stale_categories": [], "consolidation_needed": False},
        }
    }
    frame = weave(snapshot)
    assert frame.skuld.get("huginn_action") == "Fix the database"
    assert frame.verdandi.get("huginn", {}).get("priority") == "high"


def test_weave_consecutive_errors_go_to_skuld():
    snapshot = {
        "autonomy": {
            "consecutive_error_count": 5,
            "last_error": "provider_timeout",
            "ticks": 10,
        }
    }
    frame = weave(snapshot)
    assert frame.skuld.get("consecutive_errors") == 5


def test_weave_stalled_sessions_in_skuld():
    snapshot = {
        "ravens_counsel": {
            "huginn": {
                "priority": "medium",
                "stalled_sessions": ["sess_aaa", "sess_bbb"],
                "attention_items": [],
                "health_warnings": [],
                "error_trend": "stable",
                "suggested_action": "check sessions",
            },
            "muninn": {"stale_categories": [], "consolidation_needed": False},
        }
    }
    frame = weave(snapshot)
    assert "stalled_sessions" in frame.skuld
    assert "sess_aaa" in frame.skuld["stalled_sessions"]


def test_weave_provider_info_in_verdandi():
    snapshot = {"provider": {"provider": "openai", "suppression_reason": ""}}
    frame = weave(snapshot)
    assert frame.verdandi.get("provider", {}).get("name") == "openai"


# ── norns_prompt ───────────────────────────────────────────────────────────────

def test_norns_prompt_has_three_sections():
    frame = NornsFrame(
        urd={"past": "old result"},
        verdandi={"now": "running"},
        skuld={"todo": "fix db"},
    )
    rendered = norns_prompt(frame)
    assert "URÐ" in rendered
    assert "VERÐANDI" in rendered
    assert "SKULD" in rendered


def test_norns_prompt_contains_data():
    frame = NornsFrame(
        urd={"last_run": "yesterday"},
        verdandi={"active": 3},
        skuld={"action": "restart workers"},
    )
    rendered = norns_prompt(frame)
    assert "yesterday" in rendered
    assert "restart workers" in rendered


def test_norns_prompt_empty_frame():
    frame = NornsFrame()
    rendered = norns_prompt(frame)
    assert "URÐ" in rendered
    assert "{}" in rendered


# ── norns_autonomy_prompt ──────────────────────────────────────────────────────

def test_norns_autonomy_prompt_roundtrip():
    snapshot = {
        "autonomy": {"ticks": 5, "run_success": 4, "run_failures": 1},
        "health": {"api": {"running": True}},
    }
    rendered = norns_autonomy_prompt(snapshot)
    assert "URÐ" in rendered
    assert "VERÐANDI" in rendered
    assert "SKULD" in rendered


def test_norns_frame_to_dict():
    frame = NornsFrame(urd={"a": 1}, verdandi={"b": 2}, skuld={"c": 3})
    d = frame.to_dict()
    assert d["urd"]["a"] == 1
    assert d["verdandi"]["b"] == 2
    assert d["skuld"]["c"] == 3

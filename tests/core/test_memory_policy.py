from __future__ import annotations

from clawlite.core.memory_policy import (
    integration_hint,
    integration_policies_snapshot,
    integration_policy,
    quality_mode_from_state,
)


def _quality_int(value, *, minimum=0, default=0):
    base = default if value is None else value
    return max(minimum, int(base or 0))


def test_quality_mode_from_state_escalates_degrading_streak_and_errors() -> None:
    assert quality_mode_from_state(100, "stable", 0, "", has_report=False) == (
        "normal",
        "quality_state_uninitialized",
    )
    assert quality_mode_from_state(68, "degrading", 2, "", has_report=True) == (
        "degraded",
        "quality_drift_or_score_warning",
    )
    assert quality_mode_from_state(80, "stable", 0, "loop timeout", has_report=True) == (
        "severe",
        "quality_tuning_error",
    )


def test_integration_policy_and_snapshot_apply_delegated_restrictions() -> None:
    snapshot = {
        "updated_at": "2026-03-17T00:00:00+00:00",
        "current": {"score": 62, "drift": {"assessment": "stable"}},
        "tuning": {"degrading_streak": 2, "last_error": ""},
    }

    delegated = integration_policy(
        snapshot=snapshot,
        actor="subagent",
        session_id="sess-123",
        quality_int=_quality_int,
    )
    agent = integration_policy(
        snapshot=snapshot,
        actor="agent",
        session_id="sess-123",
        quality_int=_quality_int,
    )
    combined = integration_policies_snapshot(
        session_id="sess-123",
        policy_resolver=lambda actor: integration_policy(
            snapshot=snapshot,
            actor=actor,
            session_id="sess-123",
            quality_int=_quality_int,
        ),
    )

    assert delegated["mode"] == "degraded"
    assert delegated["actor_class"] == "delegated"
    assert delegated["recommended_search_limit"] == 3
    assert delegated["allow_subagent_spawn"] is False
    assert agent["recommended_search_limit"] == 4
    assert combined["mode"] == "degraded"
    assert combined["quality"]["score"] == 62
    assert integration_hint(delegated)

from __future__ import annotations

from types import SimpleNamespace

from clawlite.gateway.memory_dashboard import (
    dashboard_memory_summary,
    memory_analysis_snapshot,
    memory_quality_snapshot,
)


class _FakeMonitor:
    def telemetry(self) -> dict[str, object]:
        return {"pending": 2}


class _BrokenMonitor:
    def telemetry(self) -> dict[str, object]:
        raise RuntimeError("boom")


class _FakeMemoryStore:
    def analysis_stats(self) -> dict[str, object]:
        return {"semantic": {"enabled": True}}

    def quality_state_snapshot(self) -> dict[str, object]:
        return {"tuning": {"enabled": True}}


def test_memory_dashboard_helpers_collect_analysis_and_quality() -> None:
    store = _FakeMemoryStore()
    assert memory_analysis_snapshot(store) == {"semantic": {"enabled": True}}
    assert memory_quality_snapshot(store) == {"tuning": {"enabled": True}}


def test_dashboard_memory_summary_includes_all_sections() -> None:
    payload = dashboard_memory_summary(
        memory_monitor=_FakeMonitor(),
        memory_store=_FakeMemoryStore(),
        config=SimpleNamespace(name="cfg"),
        memory_profile_snapshot_fn=lambda _cfg: {"profile": "ok"},
        memory_suggest_snapshot_fn=lambda _cfg, refresh=False: {"refresh": refresh, "count": 1},
        memory_version_snapshot_fn=lambda _cfg: {"versions": []},
    )
    assert payload["monitor"] == {"pending": 2, "enabled": True}
    assert payload["analysis"] == {"semantic": {"enabled": True}}
    assert payload["profile"] == {"profile": "ok"}
    assert payload["suggestions"] == {"refresh": False, "count": 1}
    assert payload["versions"] == {"versions": []}
    assert payload["quality"] == {"tuning": {"enabled": True}}


def test_dashboard_memory_summary_fail_soft_when_monitor_errors() -> None:
    payload = dashboard_memory_summary(
        memory_monitor=_BrokenMonitor(),
        memory_store=SimpleNamespace(),
        config=SimpleNamespace(name="cfg"),
        memory_profile_snapshot_fn=lambda _cfg: {},
        memory_suggest_snapshot_fn=lambda _cfg, refresh=False: {"refresh": refresh},
        memory_version_snapshot_fn=lambda _cfg: {},
    )
    assert payload["monitor"]["enabled"] is True
    assert payload["monitor"]["error"] == "memory_monitor_unavailable"
    assert payload["analysis"] == {}
    assert payload["quality"] == {}

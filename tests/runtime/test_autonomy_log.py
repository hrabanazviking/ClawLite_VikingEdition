from __future__ import annotations

from clawlite.runtime.autonomy_log import AutonomyLog


def test_autonomy_log_persists_and_reports_recent_events(tmp_path) -> None:
    path = tmp_path / "autonomy-events.json"
    log = AutonomyLog(path=path, max_entries=4)

    log.record(
        source="channels",
        action="startup_delivery_replay",
        status="ok",
        summary="startup replay replayed=2 failed=0 skipped=1",
        metadata={"replayed": 2, "failed": 0, "skipped": 1},
        event_at="2026-03-07T00:00:00+00:00",
    )
    log.record(
        source="supervisor",
        action="component_recovery",
        status="recovered",
        summary="heartbeat recovery -> recovered",
        metadata={"component": "heartbeat"},
        event_at="2026-03-07T00:01:00+00:00",
    )

    reloaded = AutonomyLog(path=path, max_entries=4)
    snapshot = reloaded.snapshot(limit=4)

    assert snapshot["enabled"] is True
    assert snapshot["path"] == str(path)
    assert snapshot["total"] == 2
    assert snapshot["last_event_at"] == "2026-03-07T00:01:00+00:00"
    assert snapshot["counts"]["by_source"] == {"channels": 1, "supervisor": 1}
    assert snapshot["counts"]["by_action"] == {"component_recovery": 1, "startup_delivery_replay": 1}
    assert snapshot["counts"]["by_status"] == {"ok": 1, "recovered": 1}
    assert snapshot["recent"][-1]["summary"] == "heartbeat recovery -> recovered"


def test_autonomy_log_trims_old_entries_to_max_entries(tmp_path) -> None:
    path = tmp_path / "autonomy-events.json"
    log = AutonomyLog(path=path, max_entries=2)

    log.record(source="a", action="one", status="ok", summary="first", event_at="2026-03-07T00:00:00+00:00")
    log.record(source="b", action="two", status="ok", summary="second", event_at="2026-03-07T00:01:00+00:00")
    log.record(source="c", action="three", status="failed", summary="third", event_at="2026-03-07T00:02:00+00:00")

    snapshot = log.snapshot(limit=5)

    assert snapshot["total"] == 2
    assert [row["action"] for row in snapshot["recent"]] == ["two", "three"]
    assert snapshot["counts"]["by_source"] == {"b": 1, "c": 1}

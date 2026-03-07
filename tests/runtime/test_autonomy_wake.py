from __future__ import annotations

import asyncio
import json
from pathlib import Path

from clawlite.runtime.autonomy import AutonomyWakeCoordinator


def test_autonomy_wake_coalesces_same_key_and_shares_result() -> None:
    calls = {"count": 0}
    entered = asyncio.Event()
    release = asyncio.Event()

    async def _on_wake(kind: str, payload: dict[str, object]) -> str:
        calls["count"] += 1
        entered.set()
        await release.wait()
        return f"{kind}:{payload.get('value', 'na')}"

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=10)
        await coordinator.start(_on_wake)
        try:
            first = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=10,
                    payload={"value": "once"},
                )
            )
            await asyncio.wait_for(entered.wait(), timeout=1.0)
            second = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=10,
                    payload={"value": "ignored"},
                )
            )
            release.set()
            first_result = await first
            second_result = await second
            snapshot = coordinator.status()

            assert first_result == "heartbeat:once"
            assert second_result == "heartbeat:once"
            assert calls["count"] == 1
            assert snapshot["enqueued"] == 1
            assert snapshot["coalesced"] == 1
            assert snapshot["executed_ok"] == 1
            assert snapshot["coalesced_priority_upgrades"] == 0
            assert snapshot["coalesced_payload_updates"] == 0
            assert snapshot["kind_limits"]["heartbeat"] == 1
            assert snapshot["kind_policies"]["heartbeat"]["coalesce_mode"] == "replace_latest"
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())


def test_autonomy_wake_upgrades_queued_priority_and_payload_on_coalesce() -> None:
    entered_blocker = asyncio.Event()
    release_blocker = asyncio.Event()
    order: list[str] = []

    async def _on_wake(kind: str, payload: dict[str, object]) -> str:
        order.append(kind)
        if kind == "blocker":
            entered_blocker.set()
            await release_blocker.wait()
            return "blocker"
        return f"{kind}:{payload.get('value', 'na')}"

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=10)
        await coordinator.start(_on_wake)
        try:
            blocker = asyncio.create_task(
                coordinator.submit(kind="blocker", key="blocker:1", priority=1, payload={})
            )
            await asyncio.wait_for(entered_blocker.wait(), timeout=1.0)

            first = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=50,
                    payload={"value": "once", "phase": "queued"},
                )
            )
            for _ in range(20):
                await asyncio.sleep(0.01)
                if coordinator.status()["queue_depth"] >= 1:
                    break
            else:
                raise AssertionError("queued wake did not reach the backlog")

            second = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=5,
                    payload={"value": "updated", "extra": "yes"},
                )
            )

            release_blocker.set()
            blocker_result = await blocker
            first_result = await first
            second_result = await second
            snapshot = coordinator.status()

            assert blocker_result == "blocker"
            assert first_result == "heartbeat:updated"
            assert second_result == "heartbeat:updated"
            assert order == ["blocker", "heartbeat"]
            assert snapshot["enqueued"] == 2
            assert snapshot["coalesced"] == 1
            assert snapshot["coalesced_priority_upgrades"] == 1
            assert snapshot["coalesced_payload_updates"] == 1
            assert snapshot["by_kind"]["heartbeat"]["coalesced_priority_upgrades"] == 1
            assert snapshot["by_kind"]["heartbeat"]["coalesced_payload_updates"] == 1
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())


def test_autonomy_wake_heartbeat_replace_latest_drops_stale_payload_keys() -> None:
    entered_blocker = asyncio.Event()
    release_blocker = asyncio.Event()

    async def _on_wake(kind: str, payload: dict[str, object]) -> dict[str, object]:
        if kind == "blocker":
            entered_blocker.set()
            await release_blocker.wait()
            return {"kind": kind}
        return dict(payload)

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=10)
        await coordinator.start(_on_wake)
        try:
            blocker = asyncio.create_task(
                coordinator.submit(kind="blocker", key="blocker:1", priority=1, payload={})
            )
            await asyncio.wait_for(entered_blocker.wait(), timeout=1.0)

            first = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=20,
                    payload={"value": "first", "stale": "drop-me"},
                )
            )
            for _ in range(20):
                await asyncio.sleep(0.01)
                if coordinator.status()["queue_depth"] >= 1:
                    break
            else:
                raise AssertionError("queued heartbeat did not reach backlog")

            second = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=10,
                    payload={"value": "second"},
                )
            )

            release_blocker.set()
            await blocker
            first_result = await first
            second_result = await second

            assert first_result == {"value": "second"}
            assert second_result == {"value": "second"}
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())


def test_autonomy_wake_prioritizes_high_before_low_after_blocker() -> None:
    entered_blocker = asyncio.Event()
    release_blocker = asyncio.Event()
    order: list[str] = []

    async def _on_wake(kind: str, payload: dict[str, object]) -> str:
        del payload
        order.append(kind)
        if kind == "blocker":
            entered_blocker.set()
            await release_blocker.wait()
        return kind

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=10)
        await coordinator.start(_on_wake)
        try:
            blocker = asyncio.create_task(
                coordinator.submit(kind="blocker", key="blocker:1", priority=30, payload={})
            )
            await asyncio.wait_for(entered_blocker.wait(), timeout=1.0)

            low = asyncio.create_task(coordinator.submit(kind="low", key="job:low", priority=100, payload={}))
            high = asyncio.create_task(coordinator.submit(kind="high", key="job:high", priority=1, payload={}))

            release_blocker.set()
            blocker_result = await blocker
            high_result = await high
            low_result = await low

            assert blocker_result == "blocker"
            assert high_result == "high"
            assert low_result == "low"
            assert order == ["blocker", "high", "low"]
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())


def test_autonomy_wake_kind_quota_reserves_room_for_heartbeat() -> None:
    entered_blocker = asyncio.Event()
    release_blocker = asyncio.Event()
    order: list[str] = []

    async def _on_wake(kind: str, payload: dict[str, object]) -> str:
        del payload
        order.append(kind)
        if kind == "blocker":
            entered_blocker.set()
            await release_blocker.wait()
        return kind

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=3)
        await coordinator.start(_on_wake)
        try:
            blocker = asyncio.create_task(
                coordinator.submit(kind="blocker", key="blocker:1", priority=1, payload={})
            )
            await asyncio.wait_for(entered_blocker.wait(), timeout=1.0)

            cron_first = asyncio.create_task(
                coordinator.submit(kind="cron", key="cron:1", priority=50, payload={})
            )
            for _ in range(20):
                await asyncio.sleep(0.01)
                snapshot = coordinator.status()
                if snapshot["pending_by_kind"].get("cron", 0) >= 1:
                    break
            else:
                raise AssertionError("cron wake did not reach backlog")

            cron_second = await coordinator.submit(
                kind="cron",
                key="cron:2",
                priority=60,
                payload={},
                fallback_result="cron_quota_skipped",
            )
            heartbeat = asyncio.create_task(
                coordinator.submit(kind="heartbeat", key="heartbeat:loop", priority=10, payload={})
            )

            release_blocker.set()
            blocker_result = await blocker
            cron_first_result = await cron_first
            heartbeat_result = await heartbeat
            snapshot = coordinator.status()

            assert blocker_result == "blocker"
            assert cron_first_result == "cron"
            assert cron_second == "cron_quota_skipped"
            assert heartbeat_result == "heartbeat"
            assert order == ["blocker", "heartbeat", "cron"]
            assert snapshot["dropped_backpressure"] == 1
            assert snapshot["dropped_quota"] == 1
            assert snapshot["dropped_global_backpressure"] == 0
            assert snapshot["kind_limits"]["cron"] == 1
            assert snapshot["by_kind"]["cron"]["dropped_quota"] == 1
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())


def test_autonomy_wake_backpressure_returns_fallback_for_new_key() -> None:
    entered_first = asyncio.Event()
    release_first = asyncio.Event()

    async def _on_wake(kind: str, payload: dict[str, object]) -> str:
        del payload
        if kind == "first":
            entered_first.set()
            await release_first.wait()
        return kind

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=1)
        await coordinator.start(_on_wake)
        try:
            first_task = asyncio.create_task(
                coordinator.submit(kind="first", key="job:1", priority=5, payload={})
            )
            await asyncio.wait_for(entered_first.wait(), timeout=1.0)

            dropped = await coordinator.submit(
                kind="cron",
                key="job:2",
                priority=50,
                payload={},
                fallback_result="cron_backpressure_skipped",
            )

            release_first.set()
            first_result = await first_task
            snapshot = coordinator.status()

            assert first_result == "first"
            assert dropped == "cron_backpressure_skipped"
            assert snapshot["enqueued"] == 1
            assert snapshot["dropped_backpressure"] == 1
            assert snapshot["dropped_quota"] == 0
            assert snapshot["dropped_global_backpressure"] == 1
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())


def test_autonomy_wake_replays_pending_entries_from_journal_after_restart(tmp_path: Path) -> None:
    journal_path = tmp_path / "autonomy-wake.json"
    entered_first = asyncio.Event()
    release_first = asyncio.Event()
    restored_calls: list[tuple[str, str]] = []
    restored_done = asyncio.Event()

    async def _first_on_wake(kind: str, payload: dict[str, object]) -> str:
        if kind == "first":
            entered_first.set()
            await release_first.wait()
        return f"{kind}:{payload.get('value', 'na')}"

    async def _restored_on_wake(kind: str, payload: dict[str, object]) -> str:
        restored_calls.append((kind, str(payload.get("value", ""))))
        if len(restored_calls) >= 2:
            restored_done.set()
        return f"{kind}:{payload.get('value', 'na')}"

    async def _scenario() -> None:
        coordinator = AutonomyWakeCoordinator(max_pending=10, journal_path=journal_path)
        await coordinator.start(_first_on_wake)
        first_task = asyncio.create_task(
            coordinator.submit(kind="first", key="job:1", priority=10, payload={"value": "one"})
        )
        await asyncio.wait_for(entered_first.wait(), timeout=1.0)
        second_task = asyncio.create_task(
            coordinator.submit(kind="second", key="job:2", priority=20, payload={"value": "two"})
        )
        for _ in range(20):
            await asyncio.sleep(0.01)
            if journal_path.exists():
                journal_rows = json.loads(journal_path.read_text(encoding="utf-8"))
                if {row["key"] for row in journal_rows} == {"job:1", "job:2"}:
                    break
        else:
            raise AssertionError("journal did not persist both pending wakes")
        assert {row["key"] for row in journal_rows} == {"job:1", "job:2"}

        await coordinator.stop()
        release_first.set()
        assert await first_task is None
        assert await second_task is None

        replay = AutonomyWakeCoordinator(max_pending=10, journal_path=journal_path)
        await replay.start(_restored_on_wake)
        try:
            await asyncio.wait_for(restored_done.wait(), timeout=1.0)
            for _ in range(20):
                await asyncio.sleep(0.01)
                snapshot = replay.status()
                if snapshot["journal_entries"] == 0 and (
                    not journal_path.exists()
                    or json.loads(journal_path.read_text(encoding="utf-8")) == []
                ):
                    break
            else:
                raise AssertionError("journal cleanup did not complete")
            assert snapshot["restored"] == 2
            assert snapshot["journal_entries"] == 0
            assert snapshot["journal_path"] == str(journal_path)
            assert restored_calls == [("first", "one"), ("second", "two")]
        finally:
            await replay.stop()

    asyncio.run(_scenario())

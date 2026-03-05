from __future__ import annotations

import asyncio

from clawlite.runtime.autonomy import AutonomyWakeCoordinator


def test_autonomy_wake_coalesces_same_key_and_shares_result() -> None:
    calls = {"count": 0}

    async def _on_wake(kind: str, payload: dict[str, object]) -> str:
        calls["count"] += 1
        await asyncio.sleep(0.01)
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
            second = asyncio.create_task(
                coordinator.submit(
                    kind="heartbeat",
                    key="heartbeat:loop",
                    priority=10,
                    payload={"value": "ignored"},
                )
            )
            first_result = await first
            second_result = await second
            snapshot = coordinator.status()

            assert first_result == "heartbeat:once"
            assert second_result == "heartbeat:once"
            assert calls["count"] == 1
            assert snapshot["enqueued"] == 1
            assert snapshot["coalesced"] == 1
            assert snapshot["executed_ok"] == 1
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
        finally:
            await coordinator.stop()

    asyncio.run(_scenario())

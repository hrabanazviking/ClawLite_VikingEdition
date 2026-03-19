"""Tests for the Gjallarhorn alert broadcaster."""
from __future__ import annotations

import asyncio
import pytest

from clawlite.runtime.gjallarhorn import GjallarhornWatch


def _make_horn(**kwargs) -> tuple[GjallarhornWatch, list[tuple[str, str]]]:
    sent: list[tuple[str, str]] = []

    async def fake_send(target: str, message: str) -> None:
        sent.append((target, message))

    kwargs.setdefault("cooldown_s", 0.0)  # no cooldown in tests unless overridden
    horn = GjallarhornWatch(
        channel_target="test:123",
        **kwargs,
    )
    horn._send_fn = fake_send
    horn._running = True
    return horn, sent


# ── observe_runestone ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_block_events_accumulate():
    horn, sent = _make_horn(block_threshold=3, block_window_s=300.0)
    # Inject 3 block-kind records
    for _ in range(3):
        horn.observe_runestone({"kind": "injection_block"})
    await asyncio.sleep(0)  # let futures resolve
    assert len(sent) >= 1
    assert "injection" in sent[0][1].lower() or "block" in sent[0][1].lower()


@pytest.mark.asyncio
async def test_non_block_events_ignored():
    horn, sent = _make_horn(block_threshold=3, block_window_s=300.0)
    for _ in range(5):
        horn.observe_runestone({"kind": "volva_consolidate"})
    await asyncio.sleep(0)
    assert len(sent) == 0


@pytest.mark.asyncio
async def test_below_threshold_no_alert():
    horn, sent = _make_horn(block_threshold=5, block_window_s=300.0)
    for _ in range(4):  # one below threshold
        horn.observe_runestone({"kind": "injection_block"})
    await asyncio.sleep(0)
    assert len(sent) == 0


# ── observe_ravens ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consecutive_high_huginn_triggers_alert():
    horn, sent = _make_horn(high_tick_threshold=2)
    for _ in range(2):
        horn.observe_ravens({"huginn": {"priority": "high", "suggested_action": "fix db"}})
    await asyncio.sleep(0)
    assert len(sent) >= 1
    assert horn._consecutive_high == 2


@pytest.mark.asyncio
async def test_non_high_resets_counter():
    horn, sent = _make_horn(high_tick_threshold=3)
    horn.observe_ravens({"huginn": {"priority": "high", "suggested_action": "x"}})
    horn.observe_ravens({"huginn": {"priority": "low", "suggested_action": "y"}})
    assert horn._consecutive_high == 0


@pytest.mark.asyncio
async def test_medium_priority_does_not_trigger():
    horn, sent = _make_horn(high_tick_threshold=2)
    for _ in range(3):
        horn.observe_ravens({"huginn": {"priority": "medium", "suggested_action": "x"}})
    await asyncio.sleep(0)
    assert len(sent) == 0


# ── observe_volva ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_volva_failure_triggers_alert():
    horn, sent = _make_horn(volva_fail_threshold=2)
    horn.observe_volva({"consecutive_errors": 3, "last_error": "provider_timeout"})
    await asyncio.sleep(0)
    assert len(sent) >= 1
    assert "völva" in sent[0][1].lower() or "volva" in sent[0][1].lower() or "memory" in sent[0][1].lower()


@pytest.mark.asyncio
async def test_volva_single_error_no_alert():
    horn, sent = _make_horn(volva_fail_threshold=3)
    horn.observe_volva({"consecutive_errors": 1, "last_error": "timeout"})
    await asyncio.sleep(0)
    assert len(sent) == 0


# ── observe_autonomy ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_autonomy_errors_trigger_alert():
    horn, sent = _make_horn(autonomy_err_threshold=3)
    horn.observe_autonomy(5, "provider_quota_exceeded")
    await asyncio.sleep(0)
    assert len(sent) >= 1


@pytest.mark.asyncio
async def test_autonomy_below_threshold_no_alert():
    horn, sent = _make_horn(autonomy_err_threshold=5)
    horn.observe_autonomy(2, "minor_error")
    await asyncio.sleep(0)
    assert len(sent) == 0


# ── cooldown ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cooldown_suppresses_repeat_alerts():
    horn, sent = _make_horn(block_threshold=1, block_window_s=300.0, cooldown_s=9999.0)
    horn.observe_runestone({"kind": "injection_block"})
    await asyncio.sleep(0)
    first_count = len(sent)
    # Trigger again — should be suppressed by cooldown
    horn.observe_runestone({"kind": "injection_block"})
    await asyncio.sleep(0)
    assert len(sent) == first_count  # no new alerts


# ── ring ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ring_sends_to_target():
    horn, sent = _make_horn()
    await horn.ring("test_reason", "Test alert message")
    assert len(sent) == 1
    assert sent[0][0] == "test:123"
    assert "Test alert message" in sent[0][1]


@pytest.mark.asyncio
async def test_ring_no_target_no_send():
    sent: list = []
    async def fake_send(t, m):
        sent.append((t, m))
    horn = GjallarhornWatch(channel_target="", cooldown_s=0.0)
    horn._send_fn = fake_send
    horn._running = True
    await horn.ring("reason", "message")
    assert len(sent) == 0


# ── status ─────────────────────────────────────────────────────────────────────

def test_status_fields():
    horn = GjallarhornWatch()
    s = horn.status()
    assert "running" in s
    assert "alerts_sent" in s
    assert "consecutive_high_huginn" in s
    assert "recent_blocks" in s

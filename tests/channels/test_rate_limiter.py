"""Tests for the token bucket rate limiter in BaseChannel."""
from __future__ import annotations

import asyncio
import time

from clawlite.channels.base import BaseChannel, _TokenBucketRateLimiter


class _DummyChannel(BaseChannel):
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def send(self, *, target: str, text: str, metadata: dict | None = None) -> str:
        del target, text, metadata
        return "ok"


def test_first_message_allowed():
    rl = _TokenBucketRateLimiter(rate=5.0, per_s=60.0)
    assert rl.allow("session:abc") is True


def test_messages_allowed_up_to_rate():
    rl = _TokenBucketRateLimiter(rate=3.0, per_s=60.0)
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    # 4th should be blocked
    assert rl.allow("k") is False


def test_different_keys_independent():
    rl = _TokenBucketRateLimiter(rate=1.0, per_s=60.0)
    assert rl.allow("chan:sess1") is True
    assert rl.allow("chan:sess1") is False  # exhausted
    assert rl.allow("chan:sess2") is True   # different key, fresh bucket


def test_tokens_refill_over_time():
    rl = _TokenBucketRateLimiter(rate=2.0, per_s=1.0)  # 2 per second
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.allow("k") is False  # exhausted
    time.sleep(0.6)  # wait for ~1.2 tokens to refill
    assert rl.allow("k") is True


def test_reset_restores_bucket():
    rl = _TokenBucketRateLimiter(rate=1.0, per_s=60.0)
    rl.allow("k")  # use the token
    assert rl.allow("k") is False
    rl.reset("k")
    assert rl.allow("k") is True


def test_reset_unknown_key_safe():
    rl = _TokenBucketRateLimiter(rate=5.0, per_s=60.0)
    rl.reset("never_seen")  # should not raise


def test_zero_rate_always_blocked():
    # rate=1 minimum enforced by constructor — test the minimum
    rl = _TokenBucketRateLimiter(rate=1.0, per_s=60.0)
    assert rl.allow("k") is True
    assert rl.allow("k") is False


def test_high_rate_allows_burst():
    rl = _TokenBucketRateLimiter(rate=100.0, per_s=60.0)
    results = [rl.allow("burst") for _ in range(100)]
    assert all(results)
    assert rl.allow("burst") is False  # 101st blocked


def test_channel_rate_limiter_is_isolated_per_channel_instance():
    async def _scenario() -> None:
        first_events: list[str] = []
        second_events: list[str] = []

        async def _first_handler(session_id: str, user_id: str, text: str, metadata: dict) -> None:
            del user_id, text, metadata
            first_events.append(session_id)

        async def _second_handler(session_id: str, user_id: str, text: str, metadata: dict) -> None:
            del user_id, text, metadata
            second_events.append(session_id)

        first = _DummyChannel(name="dummy", config={}, on_message=_first_handler)
        for _ in range(11):
            await first.emit(session_id="shared", user_id="user", text="hello")
        assert len(first_events) == 10

        second = _DummyChannel(name="dummy", config={}, on_message=_second_handler)
        await second.emit(session_id="shared", user_id="user", text="hello")
        assert len(second_events) == 1

    asyncio.run(_scenario())

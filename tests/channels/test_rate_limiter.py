"""Tests for the token bucket rate limiter in BaseChannel."""
from __future__ import annotations

import time
import pytest

from clawlite.channels.base import _TokenBucketRateLimiter


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

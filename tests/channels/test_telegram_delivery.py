from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
from email.utils import format_datetime

from clawlite.channels.telegram_delivery import (
    TelegramAuthCircuitBreaker,
    coerce_retry_after_seconds,
    is_auth_failure,
    is_formatting_error,
    is_thread_not_found_error,
    is_transient_failure,
    normalize_api_message_thread_id,
    parse_target,
    retry_after_delay_s,
    sync_auth_breaker_signal_transition,
    threadless_retry_allowed,
    typing_key,
    typing_task_is_active,
)


def test_telegram_delivery_target_and_thread_helpers() -> None:
    assert parse_target("telegram:-10042:topic:9") == ("-10042", 9)
    assert parse_target("tg_42:thread:7") == ("42", 7)
    assert parse_target("42:9") == ("42", 9)
    assert parse_target("42") == ("42", None)
    assert typing_key(chat_id="42", message_thread_id=None) == "42"
    assert typing_key(chat_id="42", message_thread_id=9) == "42:9"
    assert threadless_retry_allowed(chat_id="42") is True
    assert threadless_retry_allowed(chat_id="-10042") is False
    assert normalize_api_message_thread_id(chat_id="-10042", message_thread_id=1) is None
    assert normalize_api_message_thread_id(chat_id="-10042", message_thread_id=9) == 9


def test_telegram_delivery_retry_after_parsing_supports_multiple_shapes() -> None:
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    assert coerce_retry_after_seconds(2.5) == 2.5
    assert coerce_retry_after_seconds("3") == 3.0
    assert coerce_retry_after_seconds(format_datetime(future)) is not None

    response_exc = RuntimeError("too many requests")
    response_exc.response = {"headers": {"Retry-After": "4"}}
    assert retry_after_delay_s(response_exc) == 4.0


def test_telegram_delivery_failure_classifiers_and_breaker_transition() -> None:
    class _AuthError(RuntimeError):
        status_code = 401

    class _FormattingError(RuntimeError):
        status_code = 400

    class _ThreadError(RuntimeError):
        status_code = 400

    auth_exc = _AuthError("unauthorized")
    formatting_exc = _FormattingError("can't parse entities")
    thread_exc = _ThreadError("message thread not found")

    assert is_auth_failure(auth_exc) is True
    assert is_transient_failure(TimeoutError("timed out")) is True
    assert is_formatting_error(formatting_exc) is True
    assert is_thread_not_found_error(thread_exc) is True

    breaker = TelegramAuthCircuitBreaker(failure_threshold=1, cooldown_s=60.0)
    signals = {"send_auth_breaker_close_count": 0}
    breaker.on_auth_failure()
    seen_open = sync_auth_breaker_signal_transition(
        signals=signals,
        breaker=breaker,
        key_prefix="send",
        seen_open=False,
    )
    assert seen_open is True
    breaker._open_until_monotonic = 0.0
    seen_open = sync_auth_breaker_signal_transition(
        signals=signals,
        breaker=breaker,
        key_prefix="send",
        seen_open=seen_open,
    )
    assert seen_open is False
    assert signals["send_auth_breaker_close_count"] == 1


def test_telegram_delivery_typing_task_helper_detects_active_and_cancelled() -> None:
    async def _worker() -> None:
        await asyncio.sleep(60)

    async def _scenario() -> None:
        task = asyncio.create_task(_worker())
        assert typing_task_is_active(task) is True
        task.cancel()
        assert typing_task_is_active(task) is True
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_scenario())

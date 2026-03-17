from __future__ import annotations

from types import SimpleNamespace

from clawlite.channels.telegram_status import (
    telegram_operator_status_payload,
    telegram_signals_payload,
)


def test_telegram_signals_payload_exposes_runtime_and_offset_fields() -> None:
    snapshot = SimpleNamespace(
        next_offset=42,
        safe_update_id=41,
        highest_completed_update_id=41,
        pending_count=2,
        min_pending_update_id=44,
    )

    payload = telegram_signals_payload(
        signals={"send_retry_count": 3},
        send_auth_breaker_open=True,
        typing_auth_breaker_open=False,
        typing_keepalive_active=1,
        webhook_mode_active=True,
        offset_snapshot=snapshot,
    )

    assert payload["send_retry_count"] == 3
    assert payload["send_auth_breaker_open"] is True
    assert payload["typing_auth_breaker_open"] is False
    assert payload["typing_keepalive_active"] == 1
    assert payload["webhook_mode_active"] is True
    assert payload["offset_next"] == 42
    assert payload["offset_watermark_update_id"] == 41
    assert payload["offset_pending_count"] == 2


def test_telegram_operator_status_payload_builds_transport_and_pairing_hints() -> None:
    snapshot = SimpleNamespace(
        next_offset=56,
        safe_update_id=55,
        highest_completed_update_id=55,
        pending_count=1,
        min_pending_update_id=56,
    )

    payload = telegram_operator_status_payload(
        mode="webhook",
        webhook_requested=True,
        webhook_mode_active=False,
        webhook_path="/hook",
        webhook_url_configured=False,
        webhook_secret_configured=True,
        offset_path="/tmp/offset.json",
        offset_snapshot=snapshot,
        pending_requests=[{"code": "ABC123"}],
        approved_entries=[],
        connected=False,
        running=False,
        last_error="broken",
    )

    assert payload["offset_next"] == 56
    assert payload["pairing_pending_count"] == 1
    assert any("no webhook URL is configured" in row for row in payload["hints"])
    assert any("not active" in row for row in payload["hints"])
    assert any("still pending" in row for row in payload["hints"])
    assert any("pending review" in row for row in payload["hints"])
    assert any("transport error" in row for row in payload["hints"])

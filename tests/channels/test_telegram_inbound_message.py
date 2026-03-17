from __future__ import annotations

from types import SimpleNamespace

from clawlite.channels.telegram_inbound_message import (
    extract_inbound_message_context,
    select_inbound_message,
)


def test_telegram_select_inbound_message_prefers_direct_fields() -> None:
    item = SimpleNamespace(
        message=None,
        edited_message=None,
        business_message=None,
        edited_business_message=SimpleNamespace(message_id=11),
        channel_post=None,
        edited_channel_post=None,
        effective_message=SimpleNamespace(message_id=99),
    )

    payload = select_inbound_message(item)

    assert payload is not None
    assert payload.update_kind == "edited_business_message"
    assert payload.is_edit is True
    assert payload.message.message_id == 11


def test_telegram_select_inbound_message_falls_back_to_effective_message() -> None:
    effective_message = SimpleNamespace(message_id=44)
    item = SimpleNamespace(
        message=None,
        edited_message=None,
        business_message=None,
        edited_business_message=None,
        channel_post=None,
        edited_channel_post=None,
        effective_message=effective_message,
    )

    payload = select_inbound_message(item)

    assert payload is not None
    assert payload.update_kind == "effective_message"
    assert payload.is_edit is False
    assert payload.message is effective_message


def test_telegram_extract_inbound_message_context_collects_chat_user_and_thread() -> None:
    message = SimpleNamespace(
        text=" hello ",
        caption=None,
        chat_id=-1002,
        message_id="55",
        message_thread_id="66",
        from_user=SimpleNamespace(id=77, username="alice", first_name="Alice"),
        chat=SimpleNamespace(type="supergroup"),
    )

    payload = extract_inbound_message_context(
        message,
        coerce_thread_id=lambda value: int(value) if value is not None else None,
    )

    assert payload.base_text == "hello"
    assert payload.chat_id == "-1002"
    assert payload.thread_id == 66
    assert payload.chat_type == "supergroup"
    assert payload.user_id == "77"
    assert payload.username == "alice"
    assert payload.first_name == "Alice"
    assert payload.message_id == 55

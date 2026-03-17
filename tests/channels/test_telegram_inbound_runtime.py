from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

from clawlite.channels.telegram_inbound_runtime import (
    append_unique_text,
    build_inbound_emit_payload,
    build_media_group_flush_payload,
    emit_payload_with_typing,
    media_group_key,
    merge_media_counts,
)


def test_telegram_media_group_helpers_normalize_key_text_and_counts() -> None:
    message = type("Message", (), {"chat_id": 42, "media_group_id": "album-1"})()
    rows: list[str] = []
    counts: dict[str, int] = {}

    append_unique_text(rows, " hello ")
    append_unique_text(rows, "hello")
    merge_media_counts(counts, {"Photo": 1, "video": "2", "bad": "x"})

    assert media_group_key(message) == "42:album-1"
    assert rows == ["hello"]
    assert counts == {"photo": 1, "video": 2}


def test_telegram_build_media_group_flush_payload_aggregates_metadata() -> None:
    payload = build_media_group_flush_payload(
        buffer={
            "session_id": "telegram:42",
            "user_id": "7",
            "media_group_id": "album-1",
            "texts": ["caption"],
            "media_counts": {"photo": 2},
            "media_items": [{"type": "photo", "file_id": "file-1"}],
            "message_ids": [10, 11],
            "update_ids": [100, 101],
            "metadata": {"chat_id": "42", "message_thread_id": "9"},
        },
        build_media_placeholder=lambda info: "[telegram media message: photo(2)]",
        coerce_thread_id=lambda value: int(value) if value is not None else None,
    )

    assert payload is not None
    assert payload.chat_id == "42"
    assert payload.thread_id == 9
    assert payload.text.startswith("[telegram media message: photo(2)]")
    assert payload.metadata["media_group_id"] == "album-1"
    assert payload.metadata["media_group_message_count"] == 2
    assert payload.metadata["media_total_count"] == 2


def test_telegram_build_inbound_emit_payload_collects_chat_and_thread() -> None:
    payload = build_inbound_emit_payload(
        session_id="telegram:42",
        user_id="7",
        text="hello",
        metadata={"chat_id": "42", "message_thread_id": "3"},
        coerce_thread_id=lambda value: int(value) if value is not None else None,
    )

    assert payload.session_id == "telegram:42"
    assert payload.user_id == "7"
    assert payload.chat_id == "42"
    assert payload.thread_id == 3


def test_telegram_emit_payload_with_typing_wraps_emit() -> None:
    payload = build_inbound_emit_payload(
        session_id="telegram:42",
        user_id="7",
        text="hello",
        metadata={"chat_id": "42", "message_thread_id": "5"},
        coerce_thread_id=lambda value: int(value) if value is not None else None,
    )
    start_typing = Mock()
    stop_typing = AsyncMock()
    emit = AsyncMock()

    asyncio.run(
        emit_payload_with_typing(
            payload,
            start_typing=start_typing,
            stop_typing=stop_typing,
            emit=emit,
        )
    )

    start_typing.assert_called_once_with(chat_id="42", message_thread_id=5)
    emit.assert_awaited_once()
    stop_typing.assert_awaited_once_with(chat_id="42", message_thread_id=5)

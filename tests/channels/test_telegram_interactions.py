from __future__ import annotations

from types import SimpleNamespace

from clawlite.channels.telegram_interactions import (
    callback_query_metadata,
    extract_callback_query_payload,
    extract_message_reaction_payload,
    message_reaction_metadata,
)


def test_telegram_callback_query_payload_and_metadata() -> None:
    item = SimpleNamespace(
        update_id=123,
        callback_query=SimpleNamespace(
            id="cq-1",
            data="approve:42",
            chat_instance="inst-1",
            from_user=SimpleNamespace(id=77, username="alice"),
            message=SimpleNamespace(
                message_id=88,
                message_thread_id="99",
                chat_id=-1001,
                chat=SimpleNamespace(id=-1001, type="supergroup"),
            ),
        ),
    )

    payload = extract_callback_query_payload(
        item,
        coerce_thread_id=lambda value: int(value) if value is not None else None,
    )

    assert payload is not None
    assert payload.query_id == "cq-1"
    assert payload.chat_id == "-1001"
    assert payload.chat_type == "supergroup"
    assert payload.user_id == "77"
    assert payload.thread_id == 99

    metadata = callback_query_metadata(
        payload=payload,
        callback_data="approve:42",
        callback_signed=True,
    )

    assert metadata["is_callback_query"] is True
    assert metadata["callback_query_id"] == "cq-1"
    assert metadata["callback_data"] == "approve:42"
    assert metadata["callback_signed"] is True
    assert metadata["message_id"] == 88
    assert metadata["message_thread_id"] == 99
    assert metadata["user_id"] == 77


def test_telegram_message_reaction_payload_and_metadata() -> None:
    item = SimpleNamespace(
        update_id=321,
        message_reaction=SimpleNamespace(
            chat_id=-2002,
            message_id=55,
            message_thread_id="66",
            chat=SimpleNamespace(id=-2002, type="supergroup"),
            user=SimpleNamespace(id=99, username="bob", is_bot=False),
            old_reaction=[SimpleNamespace(type="emoji", emoji="👍")],
            new_reaction=[
                SimpleNamespace(type="emoji", emoji="👍"),
                SimpleNamespace(type="emoji", emoji="🔥"),
            ],
        ),
    )

    payload = extract_message_reaction_payload(
        item,
        coerce_thread_id=lambda value: int(value) if value is not None else None,
    )

    assert payload is not None
    assert payload.chat_id == "-2002"
    assert payload.chat_type == "supergroup"
    assert payload.user_id == "99"
    assert payload.thread_id == 66
    assert payload.message_id == 55
    assert payload.is_bot is False

    reaction_text, metadata = message_reaction_metadata(
        payload=payload,
        reaction_added=["🔥"],
        reaction_new=["👍", "🔥"],
        reaction_old=["👍"],
    )

    assert reaction_text == "[telegram reaction] 🔥"
    assert metadata["is_message_reaction"] is True
    assert metadata["message_id"] == 55
    assert metadata["reaction_added"] == ["🔥"]
    assert metadata["reaction_new"] == ["👍", "🔥"]
    assert metadata["reaction_old"] == ["👍"]
    assert metadata["message_thread_id"] == 66

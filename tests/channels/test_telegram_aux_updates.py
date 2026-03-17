from __future__ import annotations

from types import SimpleNamespace

from clawlite.channels.telegram_aux_updates import extract_aux_update_event


def test_telegram_aux_updates_extract_deleted_business_messages() -> None:
    item = SimpleNamespace(
        deleted_business_messages=SimpleNamespace(
            chat=SimpleNamespace(id=42, type="private"),
            business_connection_id="bc-1",
            message_ids=[1, 2],
        )
    )

    payload = extract_aux_update_event(item)

    assert payload is not None
    assert payload.signal_key == "deleted_business_messages_received_count"
    assert payload.update_kind == "deleted_business_messages"
    assert payload.chat_id == "42"
    assert payload.extra_metadata["business_connection_id"] == "bc-1"
    assert payload.extra_metadata["message_ids"] == [1, 2]


def test_telegram_aux_updates_extract_chat_boost_and_paid_media() -> None:
    boost_item = SimpleNamespace(
        chat_boost=SimpleNamespace(
            chat=SimpleNamespace(id=-10042, type="supergroup"),
            boost=SimpleNamespace(
                boost_id="boost-1",
                source=SimpleNamespace(user=SimpleNamespace(id=7, username="alice")),
            ),
        )
    )
    paid_item = SimpleNamespace(
        purchased_paid_media=SimpleNamespace(
            chat=SimpleNamespace(id=42, type="private"),
            from_user=SimpleNamespace(id=7, username="alice"),
            payload="media-1",
        )
    )

    boost_payload = extract_aux_update_event(boost_item)
    paid_payload = extract_aux_update_event(paid_item)

    assert boost_payload is not None
    assert boost_payload.signal_key == "chat_boost_received_count"
    assert boost_payload.extra_metadata["boost_id"] == "boost-1"
    assert paid_payload is not None
    assert paid_payload.signal_key == "purchased_paid_media_received_count"
    assert paid_payload.extra_metadata["payload"] == "media-1"

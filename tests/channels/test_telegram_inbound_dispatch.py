from __future__ import annotations

from clawlite.channels.telegram import parse_command
from clawlite.channels.telegram_inbound_dispatch import build_inbound_dispatch_state


def test_telegram_inbound_dispatch_state_builds_signature_and_msg_key() -> None:
    payload = build_inbound_dispatch_state(
        text="hello world",
        chat_id="42",
        message_id=7,
        parse_command=parse_command,
        handle_commands=True,
    )

    assert payload.msg_key == ("42", 7)
    assert len(payload.signature) == 64
    assert payload.is_command is False
    assert payload.local_action is None


def test_telegram_inbound_dispatch_state_marks_local_help_action() -> None:
    payload = build_inbound_dispatch_state(
        text="/help details",
        chat_id="42",
        message_id=8,
        parse_command=parse_command,
        handle_commands=True,
    )

    assert payload.command == "help"
    assert payload.command_args == "details"
    assert payload.is_command is True
    assert payload.local_action == "help"


def test_telegram_inbound_dispatch_state_disables_local_action_when_commands_off() -> None:
    payload = build_inbound_dispatch_state(
        text="/start",
        chat_id="42",
        message_id=9,
        parse_command=parse_command,
        handle_commands=False,
    )

    assert payload.command == "start"
    assert payload.local_action is None

"""Tests for ContextWindowManager."""
from __future__ import annotations

import pytest
from clawlite.core.context_window import ContextWindowManager


def _msg(role: str, text: str) -> dict:
    return {"role": role, "content": text}


def test_trim_within_budget_unchanged():
    mgr = ContextWindowManager(budget_chars=10000)
    msgs = [_msg("system", "sys"), _msg("user", "hi"), _msg("assistant", "hello")]
    assert mgr.trim(msgs) == msgs


def test_trim_no_budget_unchanged():
    mgr = ContextWindowManager()
    msgs = [_msg("user", "A" * 500)]
    assert mgr.trim(msgs) == msgs


def test_trim_removes_old_messages():
    mgr = ContextWindowManager(budget_chars=200)
    msgs = [
        _msg("system", "You are an agent."),
        _msg("user", "A" * 100),
        _msg("assistant", "B" * 100),
        _msg("user", "C" * 100),
        _msg("assistant", "D" * 100),
        _msg("user", "latest question"),
    ]
    trimmed = mgr.trim(msgs)
    total = sum(len(m["content"]) for m in trimmed)
    assert total <= 200 * 1.1


def test_trim_preserves_system_message():
    mgr = ContextWindowManager(budget_chars=50)
    msgs = [_msg("system", "important system"), _msg("user", "X" * 200)]
    trimmed = mgr.trim(msgs)
    roles = [m["role"] for m in trimmed]
    assert "system" in roles


def test_trim_preserves_last_message():
    mgr = ContextWindowManager(budget_chars=50)
    msgs = [
        _msg("user", "A" * 200),
        _msg("assistant", "B" * 200),
        _msg("user", "latest"),
    ]
    trimmed = mgr.trim(msgs)
    assert trimmed[-1]["content"] == "latest"


def test_trim_budget_tokens():
    mgr = ContextWindowManager(budget_tokens=50)  # 50 tokens * 4 = 200 chars
    msgs = [_msg("user", "A" * 500), _msg("user", "B" * 10)]
    trimmed = mgr.trim(msgs)
    total = sum(len(m["content"]) for m in trimmed)
    assert total <= 200 * 1.1


def test_trim_empty_messages():
    mgr = ContextWindowManager(budget_chars=100)
    assert mgr.trim([]) == []


def test_trim_counts_assistant_tool_call_metadata_in_budget() -> None:
    mgr = ContextWindowManager(budget_chars=20)
    msgs = [
        _msg("user", "old"),
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": "{\"query\":\"long query for current weather in suzano sao paulo\"}",
                    },
                }
            ],
        },
        _msg("user", "latest"),
    ]

    trimmed = mgr.trim(msgs)

    assert msgs[1] not in trimmed
    assert trimmed[-1] == msgs[-1]

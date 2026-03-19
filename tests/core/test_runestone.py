"""Tests for the Runestone tamper-evident audit log."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from clawlite.core.runestone import RunestoneLog, RunestoneRecord, audit, set_runestone


def test_append_creates_file(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    log.append(kind="test_event", source="pytest", details={"x": 1})
    assert (tmp_path / "runestone.jsonl").exists()


def test_first_record_uses_genesis_prev(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    rec = log.append(kind="first", source="test")
    assert rec.prev_hash == "0" * 64


def test_second_record_links_to_first(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    r1 = log.append(kind="a", source="test")
    r2 = log.append(kind="b", source="test")
    assert r2.prev_hash == r1.this_hash


def test_seq_increments(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    r1 = log.append(kind="a", source="test")
    r2 = log.append(kind="b", source="test")
    r3 = log.append(kind="c", source="test")
    assert r1.seq == 0
    assert r2.seq == 1
    assert r3.seq == 2


def test_verify_chain_intact(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    for i in range(5):
        log.append(kind=f"e{i}", source="test", details={"i": i})
    intact, broken_at = log.verify_chain()
    assert intact is True
    assert broken_at == -1


def test_verify_chain_detects_tampering(tmp_path: Path):
    path = tmp_path / "runestone.jsonl"
    log = RunestoneLog(path)
    for i in range(3):
        log.append(kind=f"e{i}", source="test")
    # Tamper: modify first line
    lines = path.read_text().splitlines()
    first = json.loads(lines[0])
    first["kind"] = "tampered"
    lines[0] = json.dumps(first)
    path.write_text("\n".join(lines) + "\n")
    intact, broken_at = log.verify_chain()
    assert intact is False
    assert broken_at == 0


def test_tail_returns_last_n(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    for i in range(10):
        log.append(kind=f"e{i}", source="test")
    tail = log.tail(3)
    assert len(tail) == 3
    assert tail[-1]["kind"] == "e9"


def test_tail_empty_file(tmp_path: Path):
    log = RunestoneLog(tmp_path / "empty.jsonl")
    assert log.tail(5) == []


def test_state_restored_across_instances(tmp_path: Path):
    path = tmp_path / "runestone.jsonl"
    log1 = RunestoneLog(path)
    r1 = log1.append(kind="first", source="test")

    log2 = RunestoneLog(path)  # New instance reads existing file
    r2 = log2.append(kind="second", source="test")

    assert r2.seq == 1
    assert r2.prev_hash == r1.this_hash


def test_global_audit_noop_without_registration():
    """audit() should not raise even when no log is registered."""
    audit(kind="test", source="pytest", details={"safe": True})


def test_global_audit_writes_when_registered(tmp_path: Path):
    path = tmp_path / "global.jsonl"
    log = RunestoneLog(path)
    set_runestone(log)
    audit(kind="global_test", source="pytest", details={"ok": True})
    tail = log.tail(1)
    assert len(tail) == 1
    assert tail[0]["kind"] == "global_test"


def test_details_stored_in_record(tmp_path: Path):
    log = RunestoneLog(tmp_path / "runestone.jsonl")
    log.append(kind="typed", source="test", details={"threats": ["xss"], "count": 3})
    tail = log.tail(1)
    assert tail[0]["details"]["threats"] == ["xss"]
    assert tail[0]["details"]["count"] == 3

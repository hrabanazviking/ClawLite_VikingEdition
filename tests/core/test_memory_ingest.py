from __future__ import annotations
import pytest
from pathlib import Path


@pytest.fixture
def store(tmp_path):
    from clawlite.core.memory import MemoryStore
    return MemoryStore(db_path=str(tmp_path / "mem.db"), semantic_enabled=False)


def test_ingest_txt_file(store, tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("ClawLite is a Python autonomous agent runtime.")
    result = store.ingest_file(str(txt))
    assert result["ok"] is True
    assert result["modality"] == "text"
    records = store.search("autonomous agent", limit=5)
    assert any("autonomous" in r.text for r in records)


def test_ingest_md_file(store, tmp_path):
    md = tmp_path / "README.md"
    md.write_text("# ClawLite\n\nAutonomous agent with memory and tools.")
    result = store.ingest_file(str(md))
    assert result["ok"] is True
    assert result["modality"] == "text"


def test_ingest_unsupported_format_returns_error(store, tmp_path):
    unknown = tmp_path / "data.xyz"
    unknown.write_bytes(b"\x00\x01\x02")
    result = store.ingest_file(str(unknown))
    assert result["ok"] is False
    assert "unsupported" in result["reason"].lower()


def test_ingest_missing_file_returns_error(store):
    result = store.ingest_file("/nonexistent/path/file.txt")
    assert result["ok"] is False
    assert "not found" in result["reason"].lower() or "exist" in result["reason"].lower()

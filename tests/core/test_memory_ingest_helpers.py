from __future__ import annotations

from email.message import Message
from pathlib import Path

from clawlite.core.memory_ingest import memory_text_from_file, memory_text_from_url


def test_memory_text_from_file_returns_text_excerpt(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("  hello   from   clawlite \n\n memory  ", encoding="utf-8")

    text = memory_text_from_file(
        str(note),
        modality="text",
        metadata=None,
        text_like_suffixes={".txt", ".md"},
    )

    assert text == "hello from clawlite memory"


def test_memory_text_from_file_falls_back_to_reference_with_metadata(tmp_path: Path) -> None:
    image = tmp_path / "photo.png"
    image.write_bytes(b"not-a-real-image")

    text = memory_text_from_file(
        str(image),
        modality="image",
        metadata={"caption": "board sketch"},
        text_like_suffixes={".txt", ".md"},
    )

    assert "Ingested image file reference" in text
    assert "OCR hook unavailable" in text
    assert "board sketch" in text


def test_memory_text_from_url_extracts_html_text(monkeypatch) -> None:
    class _Response:
        def __init__(self) -> None:
            self.headers = Message()
            self.headers.add_header("Content-Type", "text/html; charset=utf-8")

        def read(self, _limit: int) -> bytes:
            return b"<html><body><h1>Hello</h1><script>bad()</script><p>world</p></body></html>"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=6.0: _Response())

    text = memory_text_from_url("https://example.com/page", modality="document", metadata=None)

    assert text == "Hello world"


def test_memory_text_from_url_falls_back_to_reference_on_error() -> None:
    text = memory_text_from_url(
        "https://example.com/data.json",
        modality="document",
        metadata={"summary": "backup summary"},
    )

    assert "Ingested document URL reference" in text
    assert "backup summary" in text

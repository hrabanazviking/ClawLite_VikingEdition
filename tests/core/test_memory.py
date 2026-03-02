from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from clawlite.core.memory import MemoryStore


def test_memory_store_add_and_search(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    store.add("I like python and async systems", source="user")
    store.add("Weather in Sao Paulo is warm", source="user")

    found = store.search("python", limit=3)
    assert found
    assert "python" in found[0].text.lower()


def test_memory_consolidate(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    row = store.consolidate([
        {"role": "user", "content": "remember my timezone"},
        {"role": "assistant", "content": "ok timezone set"},
    ])
    assert row is not None
    assert "timezone" in row.text


def test_memory_consolidate_skips_trivial_exchange(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    row = store.consolidate([
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "done"},
    ])
    assert row is None
    assert store.all() == []


def test_memory_consolidate_deduplicates_by_source_checkpoint(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    messages = [
        {"role": "user", "content": "remember that my timezone is UTC-3"},
        {"role": "assistant", "content": "noted, timezone preference stored"},
    ]
    first = store.consolidate(messages, source="session:abc")
    second = store.consolidate(messages, source="session:abc")
    assert first is not None
    assert second is None
    assert len(store.all()) == 1


def test_memory_consolidate_updates_curated_layer(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    store.consolidate(
        [
            {"role": "user", "content": "remember that I prefer concise answers"},
            {"role": "assistant", "content": "noted preference: concise answers"},
        ],
        source="session:42",
    )
    curated_rows = store.curated()
    assert curated_rows
    assert any("concise" in row.text.lower() for row in curated_rows)
    found = store.search("preference concise", limit=3)
    assert found
    assert any(row.source.startswith("curated:") for row in found)


def test_memory_search_prefers_overlap_even_with_negative_bm25(tmp_path: Path, monkeypatch) -> None:
    class _FakeBM25:
        def __init__(self, _corpus: object) -> None:
            pass

        def get_scores(self, _query_tokens: object) -> list[float]:
            # Simulates BM25 score inversion in tiny corpora:
            # matching row gets negative score and non-matching row gets 0.
            return [-0.3, 0.0]

    monkeypatch.setattr("clawlite.core.memory.BM25Okapi", _FakeBM25)

    store = MemoryStore(tmp_path / "memory.jsonl")
    store.add("I like python and async systems", source="user")
    store.add("Weather in Sao Paulo is warm", source="user")

    found = store.search("python", limit=1)
    assert found
    assert "python" in found[0].text.lower()


def test_memory_add_is_concurrency_safe(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")

    def _writer(idx: int) -> None:
        store.add(f"remember preference {idx}", source="load")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_writer, range(60)))

    rows = store.all()
    assert len(rows) == 60
    assert len({row.id for row in rows}) == 60

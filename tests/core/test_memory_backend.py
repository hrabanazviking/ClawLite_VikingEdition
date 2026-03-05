from __future__ import annotations

import importlib
from pathlib import Path

from clawlite.core.memory_backend import resolve_memory_backend


def test_sqlite_memory_backend_roundtrip(tmp_path: Path) -> None:
    backend = resolve_memory_backend("sqlite")
    backend.initialize(tmp_path)

    backend.upsert_layer_record(
        layer="item",
        record_id="rec-1",
        payload={"text": "hello"},
        category="context",
        created_at="2026-03-01T00:00:00+00:00",
        updated_at="2026-03-01T00:00:00+00:00",
    )
    backend.upsert_layer_record(
        layer="resource",
        record_id="rec-2",
        payload={"text": "raw"},
        category="context",
        created_at="2026-03-01T00:00:01+00:00",
        updated_at="2026-03-01T00:00:01+00:00",
    )

    rows = backend.fetch_layer_records(layer="item", limit=10)
    assert len(rows) == 1
    assert rows[0]["record_id"] == "rec-1"
    assert rows[0]["payload"]["text"] == "hello"

    deleted = backend.delete_layer_records({"rec-1"})
    assert deleted >= 1
    assert backend.fetch_layer_records(layer="item", limit=10) == []


def test_sqlite_embedding_roundtrip(tmp_path: Path) -> None:
    backend = resolve_memory_backend("sqlite")
    backend.initialize(tmp_path)

    backend.upsert_embedding(
        "emb-1",
        [0.1, 0.9],
        "2026-03-01T00:00:00+00:00",
        "user",
    )
    backend.upsert_embedding(
        "emb-2",
        [0.8, 0.2],
        "2026-03-01T00:00:01+00:00",
        "seed",
    )

    fetched_all = backend.fetch_embeddings(limit=10)
    assert fetched_all["emb-1"] == [0.1, 0.9]
    assert fetched_all["emb-2"] == [0.8, 0.2]

    fetched_filtered = backend.fetch_embeddings(record_ids=["emb-2"], limit=10)
    assert fetched_filtered == {"emb-2": [0.8, 0.2]}

    deleted = backend.delete_embeddings(["emb-1"])
    assert deleted >= 1
    remaining = backend.fetch_embeddings(limit=10)
    assert "emb-1" not in remaining
    assert remaining["emb-2"] == [0.8, 0.2]


def test_sqlite_query_similar_embeddings_returns_best_match(tmp_path: Path) -> None:
    backend = resolve_memory_backend("sqlite")
    backend.initialize(tmp_path)

    backend.upsert_embedding("alpha", [1.0, 0.0], "2026-03-01T00:00:00+00:00", "seed")
    backend.upsert_embedding("beta", [0.0, 1.0], "2026-03-01T00:00:00+00:00", "seed")
    backend.upsert_embedding("gamma", [0.5, 0.5], "2026-03-01T00:00:00+00:00", "seed")

    hits = backend.query_similar_embeddings([0.9, 0.1], limit=2)
    assert hits
    assert hits[0]["record_id"] == "alpha"
    assert float(hits[0]["score"]) > float(hits[1]["score"])


def test_pgvector_backend_remains_graceful_when_unsupported(tmp_path: Path) -> None:
    backend = resolve_memory_backend("pgvector", pgvector_url="")
    assert backend.is_supported() is False

    backend.initialize(tmp_path)
    backend.upsert_layer_record(
        layer="item",
        record_id="rec-1",
        payload={"text": "ignored"},
        category="context",
        created_at="",
        updated_at="",
    )
    backend.upsert_embedding("rec-1", [1.0, 0.0], "", "ignored")
    assert backend.fetch_layer_records(layer="item", limit=5) == []
    assert backend.fetch_embeddings(limit=5) == {}
    assert backend.query_similar_embeddings([1.0, 0.0], limit=5) == []
    assert backend.delete_layer_records(["rec-1"]) == 0
    assert backend.delete_embeddings(["rec-1"]) == 0


def test_pgvector_support_detection_requires_valid_url_and_driver(monkeypatch) -> None:
    backend_with_invalid_url = resolve_memory_backend("pgvector", pgvector_url="not-a-postgres-url")
    assert backend_with_invalid_url.is_supported() is False

    attempted_imports: list[str] = []
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name in {"psycopg", "psycopg2"}:
            attempted_imports.append(name)
            raise ImportError(f"{name} missing")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    backend_missing_drivers = resolve_memory_backend(
        "pgvector",
        pgvector_url="postgresql://user:pass@localhost:5432/clawlite",
    )
    assert backend_missing_drivers.is_supported() is False
    assert attempted_imports == ["psycopg", "psycopg2"]

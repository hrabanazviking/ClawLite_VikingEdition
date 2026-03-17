from __future__ import annotations

from types import SimpleNamespace

from clawlite.core.memory_search import rank_records, search_records


def test_search_records_uses_collect_and_rank_with_normalized_user() -> None:
    captured: dict[str, object] = {}
    row = SimpleNamespace(id="r1", text="alpha", source="session:a")

    result = search_records(
        "project alpha",
        limit=3,
        user_id="  ALICE  ",
        session_id="sess-1",
        include_shared=True,
        reasoning_layers=["fact"],
        min_confidence=0.6,
        filters={"categories": ["ops"]},
        normalize_user_id=lambda value: str(value or "").strip().lower() or "default",
        collect_retrieval_records=lambda **kwargs: (
            captured.setdefault("collect_kwargs", kwargs) and [row],
            {"r1": 1.0},
            {"r1": 2},
            [],
            True,
        ),
        rank_records_fn=lambda query, records, **kwargs: captured.setdefault(
            "rank_payload",
            {"query": query, "records": records, **kwargs},
        )
        and list(records),
    )

    assert result == [row]
    assert captured["collect_kwargs"] == {
        "user_id": "alice",
        "include_shared": True,
        "session_id": "sess-1",
        "reasoning_layers": ["fact"],
        "min_confidence": 0.6,
        "filters": {"categories": ["ops"]},
    }
    assert captured["rank_payload"] == {
        "query": "project alpha",
        "records": [row],
        "curated_importance": {"r1": 1.0},
        "curated_mentions": {"r1": 2},
        "limit": 3,
        "semantic_enabled": True,
        "session_id": "sess-1",
    }


def test_rank_records_prefers_curated_row_on_nonsemantic_tie(monkeypatch) -> None:
    class _FakeBM25:
        def __init__(self, _corpus: object) -> None:
            pass

        def get_scores(self, _query_tokens: object) -> list[float]:
            return [0.0, 0.0]

    monkeypatch.setattr("clawlite.core.memory_search.BM25Okapi", _FakeBM25)

    curated = SimpleNamespace(
        id="curated-1",
        text="project alpha notes",
        source="curated:session:a",
        confidence=1.0,
        reasoning_layer="fact",
        metadata={},
        happened_at="",
    )
    plain = SimpleNamespace(
        id="plain-1",
        text="project alpha notes",
        source="session:b",
        confidence=1.0,
        reasoning_layer="fact",
        metadata={},
        happened_at="",
    )

    ranked = rank_records(
        "project alpha",
        [plain, curated],
        curated_importance={"curated-1": 2.0},
        curated_mentions={"curated-1": 3},
        limit=2,
        semantic_enabled=False,
        session_id="",
        tokens=lambda text: [part.lower() for part in str(text or "").split()],
        extract_entities=lambda text: {},
        reasoning_intent_boosts=lambda query: {},
        query_has_temporal_intent=lambda query: False,
        generate_embedding=lambda query: None,
        query_similar_embeddings=lambda query_embedding, records: [],
        read_embeddings_map=lambda: {},
        cosine_similarity=lambda left, right: 0.0,
        entity_match_score=lambda query_entities, memory_entities: 0.0,
        recency_score=lambda created_at: 0.0,
        record_temporal_anchor=lambda row: "",
        memory_has_temporal_markers=lambda text: False,
        bounded_confidence_score=lambda value: 1.0,
        normalize_reasoning_layer=lambda value: str(value or "fact"),
        decay_penalty=lambda row: 0.0,
        upcoming_event_boost=lambda row: 0.0,
        salience_boost=lambda metadata: 0.0,
        episodic_session_boost=lambda row: 0.0,
        semantic_bm25_weight=0.4,
        semantic_vector_weight=0.6,
        ranking_confidence_boost_max=0.18,
        temporal_intent_match_boost=0.25,
        temporal_intent_miss_penalty=0.35,
    )

    assert ranked[0] is curated

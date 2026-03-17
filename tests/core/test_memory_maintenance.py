from __future__ import annotations

import asyncio
from types import SimpleNamespace

from clawlite.core.memory_maintenance import consolidate_categories, purge_decayed_records


def test_purge_decayed_records_deletes_expired_ids_and_updates_diagnostics() -> None:
    diagnostics: dict[str, object] = {}
    stale = SimpleNamespace(id="stale-1", decay_rate=5.0)

    async def _scenario() -> dict[str, int]:
        return await purge_decayed_records(
            read_history_records=lambda: [stale],
            decay_penalty=lambda row: 99.0,
            delete_records_by_ids=lambda ids: {"deleted_count": len(ids)},
            diagnostics=diagnostics,
            threshold=95.0,
        )

    payload = asyncio.run(_scenario())

    assert payload == {"purged": 1}
    assert diagnostics["decay_gc_purged"] == 1


def test_consolidate_categories_creates_summary_and_marks_rows() -> None:
    added: list[tuple[str, dict[str, object]]] = []
    upserts: list[str] = []

    class _Backend:
        def fetch_layer_records(self, *, layer: str, limit: int) -> list[dict[str, object]]:
            assert layer == "item"
            assert limit == 4000
            return [
                {
                    "layer": "item",
                    "record_id": "r1",
                    "category": "context",
                    "created_at": "2026-03-17T00:00:00+00:00",
                    "payload": {"text": "first event", "memory_type": "event", "metadata": {}},
                },
                {
                    "layer": "item",
                    "record_id": "r2",
                    "category": "context",
                    "created_at": "2026-03-17T00:01:00+00:00",
                    "payload": {"text": "second event", "memory_type": "event", "metadata": {}},
                },
            ]

        def upsert_layer_record(self, *, record_id: str, **kwargs) -> None:
            upserts.append(record_id)

    def _add_record(text: str, **kwargs) -> None:
        added.append((text, kwargs))

    async def _scenario() -> dict[str, int]:
        return await consolidate_categories(
            backend=_Backend(),
            threshold=2,
            add_record=_add_record,
            diagnostics={},
        )

    payload = asyncio.run(_scenario())

    assert payload == {"context": 2}
    assert added
    assert added[0][0].startswith("[context] 2 events:")
    assert added[0][1]["memory_type"] == "knowledge"
    assert set(upserts) == {"r1", "r2"}

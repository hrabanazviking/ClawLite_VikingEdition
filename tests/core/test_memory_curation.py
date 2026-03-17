from __future__ import annotations

import json
from pathlib import Path

from clawlite.core.memory import MemoryStore
from clawlite.core.memory_curation import update_consolidation_checkpoints


def test_update_consolidation_checkpoints_prunes_limits(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    store.checkpoints_path.write_text(
        json.dumps(
            {
                "source_signatures": {
                    "session:old-a": "sig-old-a",
                    "session:old-b": "sig-old-b",
                },
                "source_activity": {
                    "session:old-a": "2026-03-10T00:00:00+00:00",
                    "session:old-b": "2026-03-11T00:00:00+00:00",
                },
                "global_signatures": {
                    "sig-old-a": {
                        "count": 1,
                        "last_seen_at": "2026-03-10T00:00:00+00:00",
                        "last_source": "session:old-a",
                    },
                    "sig-old-b": {
                        "count": 2,
                        "last_seen_at": "2026-03-11T00:00:00+00:00",
                        "last_source": "session:old-b",
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    diagnostics: dict[str, int] = {}
    added: list[tuple[str, str]] = []

    row, repeated_count = update_consolidation_checkpoints(
        checkpoints_path=store.checkpoints_path,
        source="session:new",
        signature="sig-new",
        summary="remember timezone utc-3",
        resource_text="user: remember timezone utc-3",
        parse_checkpoints=store._parse_checkpoints,
        format_checkpoints=store._format_checkpoints,
        locked_file=store._locked_file,
        flush_and_fsync=store._flush_and_fsync,
        utcnow_iso=lambda: "2026-03-17T00:00:00+00:00",
        add_record=lambda summary, resource_text: added.append((summary, resource_text)) or {"summary": summary},
        diagnostics=diagnostics,
        max_checkpoint_sources=2,
        max_checkpoint_signatures=2,
    )

    assert row == {"summary": "remember timezone utc-3"}
    assert repeated_count == 1
    assert added == [("remember timezone utc-3", "user: remember timezone utc-3")]
    assert diagnostics["consolidate_writes"] == 1

    payload = json.loads(store.checkpoints_path.read_text(encoding="utf-8"))
    assert sorted(payload["source_signatures"]) == ["session:new", "session:old-b"]
    assert sorted(payload["global_signatures"]) == ["sig-new", "sig-old-b"]


def test_memory_consolidate_user_scope_updates_scoped_curated_layer(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")

    row = store.consolidate(
        [
            {"role": "user", "content": "remember that I prefer concise status updates"},
            {"role": "assistant", "content": "noted preference: concise status updates"},
        ],
        source="session:alice",
        user_id="alice",
    )

    assert row is not None
    user_scope = store._scope_paths(user_id="alice", shared=False)
    scoped_curated_payload = json.loads(user_scope["curated"].read_text(encoding="utf-8"))
    assert any("concise" in str(item.get("text", "")).lower() for item in scoped_curated_payload["facts"])

    global_curated_payload = json.loads(store.curated_path.read_text(encoding="utf-8"))
    assert global_curated_payload["facts"] == []

    found = store.search("concise status", user_id="alice", limit=3)
    assert found
    assert any(item.source.startswith("curated:") for item in found)

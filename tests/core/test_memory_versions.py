from __future__ import annotations

import gzip
import json
from pathlib import Path

from clawlite.core.memory_versions import (
    create_memory_branch,
    diff_memory_versions,
    list_memory_branches,
    rollback_memory_version,
    write_snapshot_payload,
)


def test_write_snapshot_payload_persists_gzip_and_advances_branch_head(tmp_path: Path) -> None:
    advanced: list[tuple[str, str]] = []

    version_id = write_snapshot_payload(
        payload={"version": 1, "history": []},
        versions_path=tmp_path,
        tag="before sync",
        advance_branch=True,
        branch_name="",
        current_branch_name=lambda: "main",
        advance_branch_head=lambda branch_name, version_id: advanced.append((branch_name, version_id)),
    )

    assert advanced == [("main", version_id)]
    version_path = tmp_path / f"{version_id}.json.gz"
    assert version_path.exists()
    with gzip.open(version_path, "rt", encoding="utf-8") as fh:
        assert json.load(fh) == {"version": 1, "history": []}


def test_diff_memory_versions_reports_added_removed_and_changed(tmp_path: Path) -> None:
    left = tmp_path / "left.json.gz"
    right = tmp_path / "right.json.gz"
    with gzip.open(left, "wt", encoding="utf-8") as fh:
        json.dump(
            {"history": [{"id": "a", "text": "same"}, {"id": "b", "text": "before"}, {"id": "c", "text": "gone"}]},
            fh,
        )
    with gzip.open(right, "wt", encoding="utf-8") as fh:
        json.dump(
            {"history": [{"id": "a", "text": "same"}, {"id": "b", "text": "after"}, {"id": "d", "text": "new"}]},
            fh,
        )

    payload = diff_memory_versions(versions_path=tmp_path, version_a="left", version_b="right")

    assert payload["added"] == {"d": "new"}
    assert payload["removed"] == {"c": "gone"}
    assert payload["changed"] == {"b": {"from": "before", "to": "after"}}
    assert payload["counts"] == {"added": 1, "removed": 1, "changed": 1}


def test_rollback_memory_version_loads_payload_and_calls_importer(tmp_path: Path) -> None:
    version_path = tmp_path / "seed.json.gz"
    with gzip.open(version_path, "wt", encoding="utf-8") as fh:
        json.dump({"history": [{"id": "seed", "text": "hello"}]}, fh)

    imported: list[dict[str, object]] = []
    rollback_memory_version(
        version_id="seed",
        versions_path=tmp_path,
        import_payload=lambda payload: imported.append(payload),
    )

    assert imported == [{"history": [{"id": "seed", "text": "hello"}]}]


def test_branch_helpers_create_and_list_branch_metadata() -> None:
    meta = {"current": "main", "branches": {"main": {"head": "seed"}}}
    saved: list[dict[str, object]] = []
    synced: list[bool] = []

    created = create_memory_branch(
        name="feature x",
        from_version="",
        checkout=True,
        load_branches_metadata=lambda: meta,
        save_branches_metadata=lambda payload: saved.append(dict(payload)),
        sync_branch_head_file=lambda: synced.append(True),
        current_branch_head=lambda: "seed",
        utcnow_iso=lambda: "2026-03-17T00:00:00+00:00",
    )

    listed = list_memory_branches(load_branches_metadata=lambda: meta)

    assert created["name"] == "feature-x"
    assert created["head"] == "seed"
    assert created["current"] == "feature-x"
    assert listed["current"] == "feature-x"
    assert "feature-x" in listed["branches"]
    assert saved
    assert synced == [True]

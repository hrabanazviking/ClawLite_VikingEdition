from __future__ import annotations

import json
from pathlib import Path

from clawlite.core.memory_quality import (
    merge_quality_tuning_state,
    quality_state_snapshot,
)


def test_quality_state_snapshot_normalizes_current_history_and_tuning(tmp_path: Path) -> None:
    path = tmp_path / "quality-state.json"
    path.write_text(
        json.dumps(
            {
                "updated_at": "2026-03-17T00:00:00+00:00",
                "baseline": {"score": 90},
                "current": {"score": 80},
                "history": [{"score": 90}, {"score": 80}],
                "tuning": {"degrading_streak": "2"},
            }
        ),
        encoding="utf-8",
    )

    payload = quality_state_snapshot(
        quality_state_path=path,
        load_json_dict=lambda target, fallback: json.loads(target.read_text(encoding="utf-8")),
        default_quality_state=lambda: {"baseline": {}, "current": {}, "history": [], "tuning": {}},
        normalize_quality_tuning_state=lambda raw: {"normalized": raw.get("degrading_streak", 0)},
    )

    assert payload["baseline"] == {"score": 90}
    assert payload["current"] == {"score": 80}
    assert len(payload["history"]) == 2
    assert payload["tuning"] == {"normalized": "2"}


def test_merge_quality_tuning_state_appends_recent_actions_and_coerces_fields() -> None:
    def _normalize(raw):
        payload = dict(raw) if isinstance(raw, dict) else {}
        rows = payload.get("recent_actions", [])
        return {
            "degrading_streak": int(payload.get("degrading_streak", 0) or 0),
            "last_action": str(payload.get("last_action", "") or ""),
            "last_action_at": str(payload.get("last_action_at", "") or ""),
            "last_action_status": str(payload.get("last_action_status", "") or ""),
            "last_reason": str(payload.get("last_reason", "") or ""),
            "next_run_at": str(payload.get("next_run_at", "") or ""),
            "last_run_at": str(payload.get("last_run_at", "") or ""),
            "last_error": str(payload.get("last_error", "") or ""),
            "recent_actions": [dict(row) if isinstance(row, dict) else {"action": str(row)} for row in rows][-3:],
        }

    merged = merge_quality_tuning_state(
        current={"degrading_streak": 1, "recent_actions": [{"action": "a1"}]},
        patch={"degrading_streak": "3", "recent_actions": [{"action": "a2"}, {"action": "a3"}]},
        normalize_quality_tuning_state=_normalize,
        quality_int=lambda value, minimum=0, default=0: max(minimum, int(value if value is not None else default)),
    )

    assert merged["degrading_streak"] == 3
    assert merged["recent_actions"] == [{"action": "a1"}, {"action": "a2"}, {"action": "a3"}]

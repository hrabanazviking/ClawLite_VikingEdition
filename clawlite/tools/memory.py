from __future__ import annotations

import json
from typing import Any

from clawlite.core.memory import MemoryRecord, MemoryStore
from clawlite.tools.base import Tool, ToolContext


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _memory_ref(memory_id: str) -> str:
    clean = str(memory_id or "").strip()
    short = clean[:8] if clean else "unknown"
    return f"mem:{short}"


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class MemoryRecallTool(Tool):
    name = "memory_recall"
    description = "Recall semantically related memory snippets with provenance refs."

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for memory retrieval."},
                "limit": {"type": "integer", "description": "Max results (clamped to 1..20)."},
                "include_metadata": {"type": "boolean", "description": "Include id/source/created_at fields."},
            },
            "required": ["query"],
        }

    async def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        del ctx
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")

        limit = _clamp_int(arguments.get("limit"), default=6, minimum=1, maximum=20)
        include_metadata = _coerce_bool(arguments.get("include_metadata"), default=True)
        rows = self.memory.search(query, limit=limit)

        results: list[dict[str, Any]] = []
        for row in rows:
            item: dict[str, Any] = {
                "ref": _memory_ref(row.id),
                "text": str(row.text or ""),
            }
            if include_metadata:
                item["id"] = str(row.id or "")
                item["source"] = str(row.source or "")
                item["created_at"] = str(row.created_at or "")
            results.append(item)

        payload = {
            "status": "ok",
            "query": query,
            "count": len(results),
            "results": results,
        }
        return _dump_json(payload)


class MemoryLearnTool(Tool):
    name = "memory_learn"
    description = "Store a durable memory note with a source marker."

    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Memory text to store."},
                "source": {"type": "string", "description": "Optional explicit source marker."},
            },
            "required": ["text"],
        }

    async def run(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        text = str(arguments.get("text", "")).strip()
        if not text:
            raise ValueError("text is required")
        text = text[:4000]

        source = str(arguments.get("source", "")).strip() or f"memory_learn:{ctx.session_id}"
        row: MemoryRecord = self.memory.add(text, source=source)

        payload = {
            "status": "ok",
            "ref": _memory_ref(row.id),
            "id": row.id,
            "source": row.source,
            "created_at": row.created_at,
            "chars": len(row.text),
        }
        return _dump_json(payload)

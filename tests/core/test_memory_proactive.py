from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

from clawlite.core.memory import MemoryStore


def test_memory_retrieve_llm_normalizes_next_step_query_shape(tmp_path: Path, monkeypatch) -> None:
    async def _scenario() -> None:
        store = MemoryStore(tmp_path / "memory.jsonl")
        store.add("project gamma release checklist includes rollback", source="session:cli:profile")

        async def _json_completion(**kwargs):
            del kwargs
            payload = {
                "answer": "Gamma release has a rollback checklist.",
                "next_step_query": "   Should we validate rollback ownership now?   ",
            }
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

        monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(acompletion=_json_completion))
        llm = await store.retrieve("gamma rollback", method="llm", limit=3)

        assert llm["method"] == "llm"
        assert llm["metadata"]["fallback_to_rag"] is False
        assert llm["next_step_query"] == "Should we validate rollback ownership now?"
        assert llm["count"] >= 1

    asyncio.run(_scenario())

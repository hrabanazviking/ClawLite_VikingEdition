from __future__ import annotations
import time
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.recall = MagicMock(return_value=[
        MagicMock(text="ClawLite uses FastAPI"),
        MagicMock(text="LiteLLM handles providers"),
    ])
    return mem


def test_proactive_loader_warms_cache(mock_memory):
    from clawlite.core.memory_proactive import ProactiveContextLoader
    loader = ProactiveContextLoader(memory=mock_memory, cache_ttl_s=30)
    results = loader.warm("What providers does ClawLite use?", session_id="s1")
    assert isinstance(results, list) and len(results) >= 1


def test_proactive_loader_cache_hit_skips_recall(mock_memory):
    from clawlite.core.memory_proactive import ProactiveContextLoader
    loader = ProactiveContextLoader(memory=mock_memory, cache_ttl_s=30)
    loader.warm("same query", session_id="s1")
    count = mock_memory.recall.call_count
    loader.warm("same query", session_id="s1")
    assert mock_memory.recall.call_count == count


def test_proactive_loader_cache_expires(mock_memory):
    from clawlite.core.memory_proactive import ProactiveContextLoader
    loader = ProactiveContextLoader(memory=mock_memory, cache_ttl_s=0.05)
    loader.warm("query", session_id="s1")
    first = mock_memory.recall.call_count
    time.sleep(0.1)
    loader.warm("query", session_id="s1")
    assert mock_memory.recall.call_count > first


def test_proactive_loader_returns_empty_on_memory_error():
    from clawlite.core.memory_proactive import ProactiveContextLoader
    mem = MagicMock()
    mem.recall = MagicMock(side_effect=RuntimeError("db error"))
    loader = ProactiveContextLoader(memory=mem, cache_ttl_s=30)
    assert loader.warm("query", session_id="s1") == []


def test_proactive_loader_timeout_returns_empty():
    from clawlite.core.memory_proactive import ProactiveContextLoader
    def slow_recall(*a, **kw):
        time.sleep(2.0)
        return []
    mem = MagicMock()
    mem.recall = MagicMock(side_effect=slow_recall)
    loader = ProactiveContextLoader(memory=mem, cache_ttl_s=30, timeout_s=0.1)
    assert loader.warm("query", session_id="s1") == []

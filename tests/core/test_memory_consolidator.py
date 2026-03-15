from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_records():
    records = []
    for i in range(4):
        r = MagicMock()
        r.text = f"Memory fact {i}: ClawLite has feature {i}"
        r.id = f"rec-{i}"
        r.category = "tech"
        records.append(r)
    return records


@pytest.mark.asyncio
async def test_consolidator_uses_llm_when_available(mock_records):
    from clawlite.core.memory_consolidator import LLMConsolidator
    run_llm = AsyncMock(return_value="ClawLite has features 0-3.")
    consolidator = LLMConsolidator(run_llm=run_llm)
    result = await consolidator.consolidate(mock_records, category="tech")
    assert result is not None and len(result) > 5
    run_llm.assert_called_once()


@pytest.mark.asyncio
async def test_consolidator_falls_back_on_llm_error(mock_records):
    from clawlite.core.memory_consolidator import LLMConsolidator
    run_llm = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    consolidator = LLMConsolidator(run_llm=run_llm)
    result = await consolidator.consolidate(mock_records, category="tech")
    assert result is not None and len(result) > 0


@pytest.mark.asyncio
async def test_consolidator_without_llm_uses_deterministic(mock_records):
    from clawlite.core.memory_consolidator import LLMConsolidator
    consolidator = LLMConsolidator(run_llm=None)
    result = await consolidator.consolidate(mock_records, category="tech")
    assert result is not None and "Memory fact" in result


@pytest.mark.asyncio
async def test_consolidator_empty_records_returns_none():
    from clawlite.core.memory_consolidator import LLMConsolidator
    consolidator = LLMConsolidator(run_llm=None)
    result = await consolidator.consolidate([], category="tech")
    assert result is None

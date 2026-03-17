from __future__ import annotations

import asyncio
from types import SimpleNamespace

from clawlite.gateway.engine_diagnostics import (
    engine_memory_payloads,
    engine_memory_quality_payload,
    memory_monitor_payload,
)


class _MemoryWithMethods:
    def diagnostics(self) -> dict[str, object]:
        return {"backend": "ok"}

    def analysis_stats(self) -> dict[str, object]:
        return {"semantic": {"enabled": True}}

    def integration_policies_snapshot(self, *, session_id: str = "") -> dict[str, object]:
        return {"session_id": session_id, "mode": "normal"}


class _QualityMemory:
    def __init__(self) -> None:
        self.calls = 0
        self._tuning_enabled = True

    def update_quality_state(
        self,
        *,
        retrieval_metrics: dict[str, object],
        turn_stability_metrics: dict[str, object],
        semantic_metrics: dict[str, object],
        sampled_at: str,
        reasoning_layer_metrics: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.calls += 1
        return {
            "retrieval": dict(retrieval_metrics),
            "turn": dict(turn_stability_metrics),
            "semantic": dict(semantic_metrics),
            "reasoning_layers": dict(reasoning_layer_metrics or {}),
            "sampled_at": sampled_at,
        }

    def quality_state_snapshot(self) -> dict[str, object]:
        return {"tuning": {"enabled": self._tuning_enabled, "recent_actions": []}}


def test_engine_memory_payloads_collect_method_results() -> None:
    payload = engine_memory_payloads(memory_store=_MemoryWithMethods())
    assert payload["memory"] == {"backend": "ok", "available": True}
    assert payload["memory_analysis"] == {"semantic": {"enabled": True}, "available": True}
    assert payload["memory_integration"] == {"session_id": "", "mode": "normal", "available": True}


def test_memory_monitor_payload_handles_missing_and_available_monitor() -> None:
    assert memory_monitor_payload(memory_monitor=None, proactive_runner_state={"running": False}) == {
        "enabled": False,
        "runner": {"running": False},
    }

    monitor = SimpleNamespace(telemetry=lambda: {"pending": 2})
    assert memory_monitor_payload(memory_monitor=monitor, proactive_runner_state={"running": True}) == {
        "pending": 2,
        "enabled": True,
        "runner": {"running": True},
    }


def test_engine_memory_quality_payload_uses_cache_and_refreshes_tuning() -> None:
    async def _scenario() -> None:
        memory = _QualityMemory()
        cache: dict[str, object] = {}

        async def _collect() -> tuple[dict[str, object], dict[str, object]]:
            return (
                {"enabled": True, "coverage_ratio": 0.5},
                {"weakest_layer": "hypothesis"},
            )

        first = await engine_memory_quality_payload(
            memory_store=memory,
            retrieval_metrics_snapshot={"retrieval_attempts": 3, "retrieval_hits": 2, "retrieval_rewrites": 1},
            turn_metrics_snapshot={"turns_success": 5, "turns_provider_errors": 1, "turns_cancelled": 0},
            generated_at="2026-03-17T00:00:00+00:00",
            memory_quality_cache=cache,
            collect_memory_analysis_metrics=_collect,
        )
        assert first["available"] is True
        assert first["updated"] is True
        assert memory.calls == 1

        second = await engine_memory_quality_payload(
            memory_store=memory,
            retrieval_metrics_snapshot={"retrieval_attempts": 3, "retrieval_hits": 2, "retrieval_rewrites": 1},
            turn_metrics_snapshot={"turns_success": 5, "turns_provider_errors": 1, "turns_cancelled": 0},
            generated_at="2026-03-17T00:00:01+00:00",
            memory_quality_cache=cache,
            collect_memory_analysis_metrics=_collect,
        )
        assert second["available"] is True
        assert second["state"]["tuning"]["enabled"] is True
        assert memory.calls == 1

    asyncio.run(_scenario())

from __future__ import annotations

import json
from pathlib import Path

from clawlite.workspace.loader import WorkspaceLoader


def test_workspace_bootstrap_renders_placeholders(tmp_path: Path) -> None:
    loader = WorkspaceLoader(workspace_path=tmp_path / "ws")
    created = loader.bootstrap(variables={"assistant_name": "Atlas", "user_name": "Eder"})
    assert created
    identity = (tmp_path / "ws" / "IDENTITY.md").read_text(encoding="utf-8")
    assert "Atlas" in identity
    profile = (tmp_path / "ws" / "USER.md").read_text(encoding="utf-8")
    assert "Eder" in profile


def test_workspace_system_context_includes_core_docs(tmp_path: Path) -> None:
    loader = WorkspaceLoader(workspace_path=tmp_path / "ws")
    loader.bootstrap()
    content = loader.system_context()
    assert "## IDENTITY.md" in content
    assert "## SOUL.md" in content


def test_workspace_bootstrap_lifecycle(tmp_path: Path) -> None:
    loader = WorkspaceLoader(workspace_path=tmp_path / "ws")
    loader.bootstrap()

    assert loader.should_run_bootstrap() is True
    prompt = loader.bootstrap_prompt()
    assert "First-run setup checklist" in prompt

    completed = loader.complete_bootstrap()
    assert completed is True
    assert loader.should_run_bootstrap() is False


def test_workspace_sync_templates_is_deterministic(tmp_path: Path) -> None:
    loader = WorkspaceLoader(workspace_path=tmp_path / "ws")
    first = loader.sync_templates()
    assert first["created"]

    second = loader.sync_templates()
    assert second["created"] == []
    assert second["updated"] == []

    tools_path = tmp_path / "ws" / "TOOLS.md"
    tools_path.write_text("custom", encoding="utf-8")
    third = loader.sync_templates(update_existing=False)
    assert tools_path in third["skipped"]

    fourth = loader.sync_templates(update_existing=True)
    assert tools_path in fourth["updated"]


def test_workspace_bootstrap_status_and_state_persistence(tmp_path: Path) -> None:
    loader = WorkspaceLoader(workspace_path=tmp_path / "ws")
    loader.bootstrap()

    initial = loader.bootstrap_status()
    assert initial["pending"] is True
    assert initial["bootstrap_exists"] is True
    assert initial["last_status"] == ""
    assert initial["run_count"] == 0

    assert loader.record_bootstrap_result(status="completed", session_id="cli:bootstrap") is True
    assert loader.complete_bootstrap() is True

    final = loader.bootstrap_status()
    assert final["pending"] is False
    assert final["bootstrap_exists"] is False
    assert final["last_status"] == "completed"
    assert final["run_count"] == 1
    assert final["last_session_id"] == "cli:bootstrap"
    assert final["completed_at"]

    state_payload = json.loads((tmp_path / "ws" / "memory" / "bootstrap-state.json").read_text(encoding="utf-8"))
    assert state_payload["last_status"] == "completed"
    assert state_payload["run_count"] == 1


def test_workspace_bootstrap_not_recreated_after_completed_state(tmp_path: Path) -> None:
    loader = WorkspaceLoader(workspace_path=tmp_path / "ws")
    loader.bootstrap()
    assert (tmp_path / "ws" / "BOOTSTRAP.md").exists()

    assert loader.record_bootstrap_result(status="completed", session_id="cli:1") is True
    assert loader.complete_bootstrap() is True

    loader.sync_templates(update_existing=False)
    assert not (tmp_path / "ws" / "BOOTSTRAP.md").exists()

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TEMPLATE_FILES = (
    "IDENTITY.md",
    "SOUL.md",
    "USER.md",
    "AGENTS.md",
    "TOOLS.md",
    "HEARTBEAT.md",
    "BOOTSTRAP.md",
    "memory/MEMORY.md",
)

DEFAULT_VARS = {
    "assistant_name": "ClawLite",
    "assistant_emoji": "🦊",
    "assistant_creature": "fox",
    "assistant_vibe": "direct, pragmatic, autonomous",
    "assistant_backstory": "An autonomous personal assistant focused on execution.",
    "user_name": "Owner",
    "user_timezone": "UTC",
    "user_context": "Personal operations and software projects",
    "user_preferences": "Clear answers, direct actions, concise updates",
}


class WorkspaceLoader:
    def __init__(self, workspace_path: str | Path | None = None, template_root: str | Path | None = None) -> None:
        self.workspace = Path(workspace_path) if workspace_path else (Path.home() / ".clawlite" / "workspace")
        self.templates = Path(template_root) if template_root else Path(__file__).resolve().parent / "templates"

    @staticmethod
    def _render(template: str, variables: dict[str, str]) -> str:
        rendered = template
        for key, value in variables.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered

    def sync_templates(
        self,
        *,
        variables: dict[str, str] | None = None,
        update_existing: bool = False,
    ) -> dict[str, list[Path]]:
        values = dict(DEFAULT_VARS)
        values.update({k: str(v) for k, v in (variables or {}).items()})

        created: list[Path] = []
        updated: list[Path] = []
        skipped: list[Path] = []

        self.workspace.mkdir(parents=True, exist_ok=True)

        bootstrap_status = self.bootstrap_status()
        bootstrap_completed = bool(bootstrap_status.get("completed_at")) or str(bootstrap_status.get("last_status", "")) == "completed"

        for rel in TEMPLATE_FILES:
            src = self.templates / rel
            dst = self.workspace / rel
            if not src.exists():
                continue

            if rel == "BOOTSTRAP.md" and bootstrap_completed:
                skipped.append(dst)
                continue

            rendered = self._render(src.read_text(encoding="utf-8"), values)
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(rendered, encoding="utf-8")
                created.append(dst)
                continue

            current = dst.read_text(encoding="utf-8", errors="ignore")
            if current == rendered:
                skipped.append(dst)
                continue

            if update_existing:
                dst.write_text(rendered, encoding="utf-8")
                updated.append(dst)
            else:
                skipped.append(dst)

        return {
            "created": sorted(created),
            "updated": sorted(updated),
            "skipped": sorted(skipped),
        }

    def bootstrap(self, *, variables: dict[str, str] | None = None, overwrite: bool = False) -> list[Path]:
        result = self.sync_templates(variables=variables, update_existing=overwrite)
        return [*result["created"], *result["updated"]]

    def read(self, filenames: Iterable[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for filename in filenames:
            path = self.workspace / filename
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if text:
                out[filename] = text
        return out

    def bootstrap_path(self) -> Path:
        return self.workspace / "BOOTSTRAP.md"

    def bootstrap_state_path(self) -> Path:
        return self.workspace / "memory" / "bootstrap-state.json"

    @staticmethod
    def _bootstrap_state_defaults() -> dict[str, Any]:
        return {
            "last_run_iso": "",
            "completed_at": "",
            "last_status": "",
            "last_error": "",
            "run_count": 0,
            "last_session_id": "",
        }

    def _read_bootstrap_state(self) -> dict[str, Any]:
        defaults = self._bootstrap_state_defaults()
        path = self.bootstrap_state_path()
        if not path.exists():
            return dict(defaults)
        try:
            payload = json.loads(path.read_text(encoding="utf-8").strip() or "{}")
        except Exception:
            return dict(defaults)
        if not isinstance(payload, dict):
            return dict(defaults)

        state = dict(defaults)
        state["last_run_iso"] = str(payload.get("last_run_iso", "") or "")
        state["completed_at"] = str(payload.get("completed_at", "") or "")
        state["last_status"] = str(payload.get("last_status", "") or "")
        state["last_error"] = str(payload.get("last_error", "") or "")
        state["last_session_id"] = str(payload.get("last_session_id", "") or "")
        try:
            state["run_count"] = max(0, int(payload.get("run_count", 0) or 0))
        except Exception:
            state["run_count"] = 0
        return state

    def _write_bootstrap_state(self, payload: dict[str, Any]) -> bool:
        path = self.bootstrap_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                delete=False,
                prefix=".bootstrap-state-",
                suffix=".tmp",
            ) as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                temp_path = Path(handle.name)
            if temp_path is None:
                return False
            temp_path.replace(path)
            return True
        except Exception:
            if temp_path is not None and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            return False

    def bootstrap_status(self) -> dict[str, Any]:
        state = self._read_bootstrap_state()
        bootstrap_path = self.bootstrap_path()
        exists = bootstrap_path.exists()
        has_content = False
        if exists:
            try:
                has_content = bool(bootstrap_path.read_text(encoding="utf-8", errors="ignore").strip())
            except Exception:
                has_content = False
        completed = bool(state.get("completed_at")) or str(state.get("last_status", "")) == "completed"
        pending = bool(exists and has_content and not completed)
        return {
            "pending": pending,
            "bootstrap_exists": exists,
            "bootstrap_path": str(bootstrap_path),
            "state_path": str(self.bootstrap_state_path()),
            "last_run_iso": str(state.get("last_run_iso", "") or ""),
            "completed_at": str(state.get("completed_at", "") or ""),
            "last_status": str(state.get("last_status", "") or ""),
            "last_error": str(state.get("last_error", "") or ""),
            "run_count": int(state.get("run_count", 0) or 0),
            "last_session_id": str(state.get("last_session_id", "") or ""),
        }

    def record_bootstrap_result(self, status: str, session_id: str = "", error: str = "") -> bool:
        state = self._read_bootstrap_state()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        normalized_status = str(status or "").strip().lower() or "unknown"

        state["last_run_iso"] = now
        state["last_status"] = normalized_status
        state["last_error"] = str(error or "")
        state["last_session_id"] = str(session_id or "")
        state["run_count"] = max(0, int(state.get("run_count", 0) or 0)) + 1
        if normalized_status == "completed":
            state["completed_at"] = now

        payload = {
            "last_run_iso": str(state.get("last_run_iso", "") or ""),
            "completed_at": str(state.get("completed_at", "") or ""),
            "last_status": str(state.get("last_status", "") or ""),
            "last_error": str(state.get("last_error", "") or ""),
            "run_count": int(state.get("run_count", 0) or 0),
            "last_session_id": str(state.get("last_session_id", "") or ""),
        }
        return self._write_bootstrap_state(payload)

    def should_run_bootstrap(self) -> bool:
        return bool(self.bootstrap_status().get("pending", False))

    def bootstrap_prompt(self) -> str:
        if not self.should_run_bootstrap():
            return ""
        path = self.bootstrap_path()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore").strip()

    def complete_bootstrap(self) -> bool:
        path = self.bootstrap_path()
        if not path.exists():
            return False
        path.unlink()
        return True

    def heartbeat_prompt(self) -> str:
        path = self.workspace / "HEARTBEAT.md"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore").strip()

    def system_context(self, *, include_heartbeat: bool = True, include_bootstrap: bool = True) -> str:
        files = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "TOOLS.md", "USER.md"]
        if include_heartbeat:
            files.append("HEARTBEAT.md")
        if include_bootstrap and self.should_run_bootstrap():
            files.append("BOOTSTRAP.md")

        docs = self.read(files)
        ordered_files = [name for name in files if name in docs]
        parts = [f"## {name}\n{docs[name]}" for name in ordered_files]
        return "\n\n".join(parts).strip()

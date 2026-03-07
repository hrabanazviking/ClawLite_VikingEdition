from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clawlite.runtime.self_evolution import Validator


def test_validator_prefers_project_venv_python_for_ruff_and_pytest(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    venv_python = project_root / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("", encoding="utf-8")

    calls: list[tuple[list[str], dict[str, object]]] = []

    def _fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((list(args), dict(kwargs)))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    with patch("clawlite.runtime.self_evolution.subprocess.run", side_effect=_fake_run):
        validator = Validator(project_root)
        ruff_ok, _ = validator.run_ruff()
        pytest_ok, _ = validator.run_pytest()

    assert ruff_ok is True
    assert pytest_ok is True
    assert calls[0][0][:4] == [str(venv_python), "-m", "ruff", "check"]
    assert "--fix" not in calls[0][0]
    assert calls[0][1]["cwd"] == str(project_root)
    assert calls[1][0][:3] == [str(venv_python), "-m", "pytest"]
    assert calls[1][1]["cwd"] == str(project_root)


def test_validator_fails_closed_when_python_executable_is_missing(tmp_path: Path) -> None:
    validator = Validator(tmp_path, python_executable=tmp_path / "missing-python")

    with patch("clawlite.runtime.self_evolution.subprocess.run", side_effect=FileNotFoundError):
        ruff_ok, ruff_output = validator.run_ruff()
        pytest_ok, pytest_output = validator.run_pytest()

    assert ruff_ok is False
    assert "python executable not found" in ruff_output
    assert pytest_ok is False
    assert "python executable not found" in pytest_output

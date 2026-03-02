from __future__ import annotations

from pathlib import Path

from clawlite.core.skills import SkillsLoader


def test_skills_loader_discovers_skill_md(tmp_path: Path) -> None:
    skill_dir = tmp_path / "hello"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: hello\ndescription: test skill\nalways: true\nrequires: curl,git\n---\n",
        encoding="utf-8",
    )

    loader = SkillsLoader(builtin_root=tmp_path)
    found = loader.discover()
    assert len(found) == 1
    assert found[0].name == "hello"
    assert found[0].always is True
    assert "curl" in found[0].requires


def test_skills_loader_marks_unavailable_when_requirements_missing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "gh"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: github\n"
        "description: github skill\n"
        "always: false\n"
        'metadata: {"nanobot":{"requires":{"bins":["definitely-not-a-real-bin-xyz"]}}}\n'
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    loader = SkillsLoader(builtin_root=tmp_path)
    all_rows = loader.discover(include_unavailable=True)
    assert len(all_rows) == 1
    assert all_rows[0].available is False
    assert any(item.startswith("bin:") for item in all_rows[0].missing)

    available = loader.discover(include_unavailable=False)
    assert available == []


def test_skills_loader_always_on_filters_unavailable(tmp_path: Path, monkeypatch) -> None:
    required_env = "TEST_CLAWLITE_SKILL_ENV"
    skill_dir = tmp_path / "always"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: always\n"
        "description: always skill\n"
        "always: true\n"
        f'metadata: {{"nanobot":{{"requires":{{"env":["{required_env}"]}}}}}}\n'
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    loader = SkillsLoader(builtin_root=tmp_path)
    monkeypatch.delenv(required_env, raising=False)
    assert loader.always_on() == []

    monkeypatch.setenv(required_env, "1")
    rows = loader.always_on()
    assert len(rows) == 1
    assert rows[0].name == "always"


def test_skills_loader_can_load_body_and_render_prompt(tmp_path: Path) -> None:
    skill_dir = tmp_path / "a"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: skill alpha\nalways: true\n---\n\n# Alpha\n\nUse alpha.\n",
        encoding="utf-8",
    )
    loader = SkillsLoader(builtin_root=tmp_path)
    content = loader.load_skill_content("alpha")
    assert content is not None
    assert "Use alpha." in content

    prompt_rows = loader.render_for_prompt()
    assert len(prompt_rows) == 1
    assert "<available_skills>" in prompt_rows[0]
    assert "<name>alpha</name>" in prompt_rows[0]
    assert "<location>" in prompt_rows[0]


def test_skills_loader_marks_invalid_execution_contract(tmp_path: Path) -> None:
    skill_dir = tmp_path / "invalid-contract"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: invalid-contract\n"
        "description: invalid binding\n"
        "command: echo hello\n"
        "script: web_search\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    loader = SkillsLoader(builtin_root=tmp_path)
    rows = loader.discover(include_unavailable=True)
    assert len(rows) == 1
    assert rows[0].available is False
    assert rows[0].execution_kind == "invalid"
    assert "contract:command_and_script_are_mutually_exclusive" in rows[0].contract_issues


def test_skills_loader_duplicate_policy_prefers_workspace_over_builtin(tmp_path: Path, monkeypatch) -> None:
    builtin = tmp_path / "builtin"
    workspace = tmp_path / ".clawlite" / "workspace" / "skills"
    marketplace = tmp_path / ".clawlite" / "marketplace" / "skills"

    (builtin / "dup").mkdir(parents=True, exist_ok=True)
    (workspace / "dup").mkdir(parents=True, exist_ok=True)
    (marketplace / "dup").mkdir(parents=True, exist_ok=True)

    (builtin / "dup" / "SKILL.md").write_text(
        "---\nname: dup\ndescription: from builtin\n---\n",
        encoding="utf-8",
    )
    (workspace / "dup" / "SKILL.md").write_text(
        "---\nname: dup\ndescription: from workspace\n---\n",
        encoding="utf-8",
    )
    (marketplace / "dup" / "SKILL.md").write_text(
        "---\nname: dup\ndescription: from marketplace\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(tmp_path))
    loader = SkillsLoader(builtin_root=builtin)
    row = loader.get("dup")
    assert row is not None
    assert row.source == "workspace"
    assert row.description == "from workspace"


def test_skills_loader_parses_multiline_metadata_json(tmp_path: Path) -> None:
    skill_dir = tmp_path / "meta"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: meta\n"
        "description: metadata parser\n"
        "metadata: {\n"
        '  "clawlite": {\n'
        '    "requires": {"env": ["TEST_MULTI_ENV"]}\n'
        "  }\n"
        "}\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    loader = SkillsLoader(builtin_root=tmp_path)
    row = loader.get("meta")
    assert row is not None
    assert "env:TEST_MULTI_ENV" in row.missing


def test_skills_loader_normalizes_requirement_schema_and_reports_invalid_env_names(tmp_path: Path) -> None:
    skill_dir = tmp_path / "schema"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: schema\n"
        "description: requirement schema\n"
        'requirements: {"bins": ["python3"], "env": ["GOOD_ENV", "bad-env"], "os": ["Linux"]}\n'
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    loader = SkillsLoader(builtin_root=tmp_path)
    row = loader.get("schema")
    assert row is not None
    assert row.requirements["os"] == ["linux"]
    assert "python3" in row.requirements["bins"]
    assert "GOOD_ENV" in row.requirements["env"]
    assert any(issue.startswith("requirements:invalid_env_name:bad-env") for issue in row.contract_issues)
    assert row.available is False

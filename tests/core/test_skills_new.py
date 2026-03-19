from __future__ import annotations

import re
from pathlib import Path

from clawlite.core.skills import SCRIPT_RUNTIME_REQUIREMENTS


def test_all_new_skills_have_valid_frontmatter() -> None:
    skills_root = Path("clawlite/skills")
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    assert skill_files, "No skill files found under clawlite/skills"

    for skill_md in skill_files:
        assert skill_md.exists(), f"Missing: {skill_md}"
        content = skill_md.read_text(encoding="utf-8")
        assert "name:" in content, f"Missing 'name:' in {skill_md}"
        assert "description:" in content, f"Missing 'description:' in {skill_md}"
        assert "script:" in content, f"Missing 'script:' in {skill_md}"
        assert "command:" not in content, f"Unexpected 'command:' in {skill_md}"


def test_all_builtin_scripts_have_runtime_requirement_mapping() -> None:
    skills_root = Path("clawlite/skills")
    script_names: set[str] = set()
    for skill_md in sorted(skills_root.glob("*/SKILL.md")):
        content = skill_md.read_text(encoding="utf-8")
        match = re.search(r"^script:\s*(\S+)", content, flags=re.MULTILINE)
        assert match is not None, f"Missing 'script:' in {skill_md}"
        script_names.add(str(match.group(1)).strip())

    mapped = set(SCRIPT_RUNTIME_REQUIREMENTS.keys())
    assert script_names <= mapped, f"Missing runtime mapping for: {sorted(script_names - mapped)}"

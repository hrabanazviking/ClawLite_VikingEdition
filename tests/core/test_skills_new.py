from __future__ import annotations

from pathlib import Path


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

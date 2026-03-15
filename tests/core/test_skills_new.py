from __future__ import annotations

from pathlib import Path


def test_all_new_skills_have_valid_frontmatter() -> None:
    new_skills = [
        "notion",
        "obsidian",
        "github-issues",
        "spotify",
        "docker",
        "1password",
        "apple-notes",
        "trello",
        "linear",
        "jira",
    ]
    for skill_name in new_skills:
        skill_md = Path("clawlite/skills") / skill_name / "SKILL.md"
        assert skill_md.exists(), f"Missing: {skill_md}"
        content = skill_md.read_text(encoding="utf-8")
        assert "name:" in content, f"Missing 'name:' in {skill_md}"
        assert "description:" in content, f"Missing 'description:' in {skill_md}"
        assert "always:" in content, f"Missing 'always:' in {skill_md}"

from __future__ import annotations
import zipfile
import pytest
from pathlib import Path


def test_init_skill_creates_skill_md(tmp_path):
    from clawlite.skills.skill_creator import init_skill
    skill_dir = init_skill("my-tool", base_path=tmp_path)
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists()
    content = skill_md.read_text()
    assert "name: my-tool" in content
    assert "description:" in content


def test_init_skill_with_scripts_dir(tmp_path):
    from clawlite.skills.skill_creator import init_skill
    skill_dir = init_skill("my-tool", base_path=tmp_path, include_scripts=True)
    assert (skill_dir / "scripts").is_dir()
    assert (skill_dir / "scripts" / "main.py").exists()


def test_normalize_skill_name():
    from clawlite.skills.skill_creator import normalize_skill_name
    assert normalize_skill_name("My Tool") == "my-tool"
    assert normalize_skill_name("my_tool") == "my-tool"
    assert normalize_skill_name("my-tool") == "my-tool"


def test_init_skill_rejects_existing(tmp_path):
    from clawlite.skills.skill_creator import init_skill
    init_skill("duplicate", base_path=tmp_path)
    with pytest.raises(FileExistsError):
        init_skill("duplicate", base_path=tmp_path)


def test_init_skill_invalid_name(tmp_path):
    from clawlite.skills.skill_creator import init_skill
    with pytest.raises(ValueError):
        init_skill("", base_path=tmp_path)


def test_package_skill_creates_zip(tmp_path):
    from clawlite.skills.skill_creator import init_skill, package_skill
    skill_dir = init_skill("my-tool", base_path=tmp_path, include_scripts=True)
    archive = package_skill(skill_dir, output_dir=tmp_path)
    assert archive.exists()
    assert archive.suffix == ".skill"
    assert archive.name == "my-tool.skill"
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
    assert "SKILL.md" in names
    assert any("scripts" in n for n in names)


def test_package_skill_rejects_missing_skill_md(tmp_path):
    from clawlite.skills.skill_creator import package_skill
    bad_dir = tmp_path / "bad-skill"
    bad_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        package_skill(bad_dir)


def test_package_skill_rejects_symlinks(tmp_path):
    from clawlite.skills.skill_creator import init_skill, package_skill
    skill_dir = init_skill("sym-skill", base_path=tmp_path)
    link = skill_dir / "bad-link"
    link.symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="Symlinks not allowed"):
        package_skill(skill_dir)

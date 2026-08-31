"""Tests for SkillRegistry and Skill SKILL.md parsing."""

import logging
import textwrap
from pathlib import Path

import pytest


SAMPLE_SKILL_MD = textwrap.dedent("""\
    ---
    name: review-pr
    description: Review a pull request by examining code quality, tests, and architecture.
    ---

    # Review PR

    When the user asks you to review a PR:
    1. Fetch the diff via `git diff main...HEAD`
    2. Check for code quality issues
    3. Verify tests exist
""")


def _write_skill(skills_dir: Path, dir_name: str, body: str) -> Path:
    skill_dir = skills_dir / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(body, encoding="utf-8")
    return skill_file


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills"
    d.mkdir()
    return d


def test_registry_loads_valid_skill(skills_dir):
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)

    reg = SkillRegistry(skills_dir=skills_dir)

    skill = reg.get("review-pr")
    assert skill is not None
    assert skill.name == "review-pr"
    assert "Review a pull request" in skill.description
    assert "When the user asks you to review a PR" in skill.body


def test_registry_loads_multiple_skills(skills_dir):
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)
    _write_skill(
        skills_dir,
        "schedule-meeting",
        textwrap.dedent("""\
            ---
            name: schedule-meeting
            description: Schedule a meeting by checking calendars and proposing times.
            ---

            # Steps
            1. List availability
            2. Propose times
        """),
    )

    reg = SkillRegistry(skills_dir=skills_dir)

    assert set(reg.skills.keys()) == {"review-pr", "schedule-meeting"}


def test_registry_skips_malformed_with_warning(skills_dir, caplog):
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "broken", "just plain text, no frontmatter")

    with caplog.at_level(logging.WARNING):
        reg = SkillRegistry(skills_dir=skills_dir)

    assert reg.skills == {}
    assert any("broken" in rec.message for rec in caplog.records)


def test_registry_skips_when_name_mismatches_dir(skills_dir, caplog):
    from mini_agent.skills import SkillRegistry

    bad = textwrap.dedent("""\
        ---
        name: different-name
        description: Mismatch test.
        ---

        body
    """)
    _write_skill(skills_dir, "dir-name", bad)

    with caplog.at_level(logging.WARNING):
        reg = SkillRegistry(skills_dir=skills_dir)

    assert reg.skills == {}


def test_registry_handles_missing_dir(tmp_path):
    from mini_agent.skills import SkillRegistry

    reg = SkillRegistry(skills_dir=tmp_path / "does-not-exist")

    assert reg.skills == {}


def test_catalog_text_format(skills_dir):
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)

    reg = SkillRegistry(skills_dir=skills_dir)
    catalog = reg.catalog_text()

    assert catalog.startswith("Available skills:\n")
    assert "- review-pr: Review a pull request" in catalog
    assert '{"skill": "name"}' in catalog


def test_catalog_text_empty_when_no_skills(tmp_path):
    from mini_agent.skills import SkillRegistry

    reg = SkillRegistry(skills_dir=tmp_path / "empty")
    assert reg.catalog_text() == ""
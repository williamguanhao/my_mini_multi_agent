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

    assert "To activate a skill" in catalog
    assert "Available skills:" in catalog
    assert "- review-pr: Review a pull request" in catalog
    assert '{"skill": "<name>"}' in catalog


def test_catalog_text_empty_when_no_skills(tmp_path):
    from mini_agent.skills import SkillRegistry

    reg = SkillRegistry(skills_dir=tmp_path / "empty")
    assert reg.catalog_text() == ""


# ---------------------------------------------------------------------------
# ContextProvider skill integration tests
# ---------------------------------------------------------------------------

import types


class _FakeSession:
    def __init__(self, session_id="test-session"):
        self.session_id = session_id


class _FakeRetriever:
    def __init__(self, messages):
        self._messages = messages

    def retrieve(self, session, query):
        return list(self._messages)


def test_context_injects_catalog_into_system(skills_dir):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)
    reg = SkillRegistry(skills_dir=skills_dir)

    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_FakeRetriever([
            {"role": "user", "content": "review my PR"},
        ]),
        skill_registry=reg,
    )

    ctx = provider.build("review my PR")
    system = ctx.messages[0]
    assert system["role"] == "system"
    assert "Available skills:" in system["content"]
    assert "- review-pr:" in system["content"]


def test_context_no_system_block_when_no_skills(tmp_path):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    reg = SkillRegistry(skills_dir=tmp_path / "empty")

    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_FakeRetriever([
            {"role": "user", "content": "hi"},
        ]),
        skill_registry=reg,
    )

    ctx = provider.build("hi")
    assert all(m["role"] != "system" for m in ctx.messages)


def test_context_activates_skill_from_history_intent(skills_dir):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)
    reg = SkillRegistry(skills_dir=skills_dir)

    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_FakeRetriever([
            {"role": "user", "content": "review my PR"},
            {
                "role": "assistant",
                "content": '{"skill": "review-pr"}\nStarting review now.',
            },
        ]),
        skill_registry=reg,
    )

    ctx = provider.build("continue")
    system = ctx.messages[0]
    assert system["role"] == "system"
    assert "# Active skill: review-pr" in system["content"]
    assert "When the user asks you to review a PR" in system["content"]


def test_context_persists_skill_across_turns(skills_dir):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)
    reg = SkillRegistry(skills_dir=skills_dir)

    class _MultiTurnRetriever:
        def __init__(self):
            self.call_count = 0

        def retrieve(self, session, query):
            self.call_count += 1
            if self.call_count == 1:
                return [
                    {"role": "user", "content": "review my PR"},
                    {"role": "assistant", "content": '{"skill": "review-pr"}\ngo'},
                ]
            return [
                {"role": "user", "content": "anything else"},
                {"role": "assistant", "content": "just continuing"},
            ]

    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_MultiTurnRetriever(),
        skill_registry=reg,
    )

    first = provider.build("review my PR")
    assert "# Active skill: review-pr" in first.messages[0]["content"]

    second = provider.build("anything else")
    assert "# Active skill: review-pr" in second.messages[0]["content"]


def test_context_unknown_skill_ignored(skills_dir):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)
    reg = SkillRegistry(skills_dir=skills_dir)

    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_FakeRetriever([
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": '{"skill": "does-not-exist"}\nwhatever',
            },
        ]),
        skill_registry=reg,
    )

    ctx = provider.build("hi")
    system = ctx.messages[0]
    assert "# Active skill:" not in system["content"]


def test_context_malformed_first_line_ignored(skills_dir):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    _write_skill(skills_dir, "review-pr", SAMPLE_SKILL_MD)
    reg = SkillRegistry(skills_dir=skills_dir)

    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_FakeRetriever([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "{not valid json at all"},
        ]),
        skill_registry=reg,
    )

    ctx = provider.build("hi")
    system = ctx.messages[0]
    assert "# Active skill:" not in system["content"]
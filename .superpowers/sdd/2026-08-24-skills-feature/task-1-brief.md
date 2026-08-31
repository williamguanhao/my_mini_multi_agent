# Task 1: Skill + SkillRegistry

**Files:**
- Create: `mini_agent/skills.py` (currently 0 bytes)
- Test: `tests/test_skills.py`

**Interfaces:**
- Produces: `Skill(name: str, description: str, body: str, path: Path)` and `SkillRegistry(skills_dir: Path) → SkillRegistry`
- `SkillRegistry.skills: dict[str, Skill]`
- `SkillRegistry.get(name) → Skill | None`
- `SkillRegistry.catalog_text() → str`

## Steps

### Step 1: Write failing tests for `SkillRegistry` parsing and catalog

Create `tests/test_skills.py`:

```python
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
```

### Step 2: Run tests to verify they fail

Run: `python -m pytest tests/test_skills.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'mini_agent.skills'`.

### Step 3: Implement `Skill` and `SkillRegistry`

Create `mini_agent/skills.py`:

```python
"""Skills registry.

A skill is a folder under `skills_dir/<kebab-name>/SKILL.md` containing
YAML frontmatter (`name`, `description`) and a markdown body.

The agent injects the catalog into its system prompt and activates a
skill when the LLM emits `{"skill": "<name>"}` as the first line of
a response. The activated skill's body is then appended to the system
prompt for the rest of the session.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


class SkillRegistry:

    def __init__(self, skills_dir: Path = Path("skills")):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self.load_all()

    def load_all(self) -> None:
        if not self.skills_dir.exists():
            return
        for entry in sorted(self.skills_dir.iterdir()):
            if not entry.is_dir():
                continue
            skill_file = entry / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                skill = self._parse(skill_file)
            except Exception as e:
                log.warning(
                    "Failed to load skill from %s: %s",
                    skill_file,
                    e,
                )
                continue
            if skill.name != entry.name:
                log.warning(
                    "Skill name '%s' does not match directory '%s' "
                    "(%s); skipping",
                    skill.name,
                    entry.name,
                    skill_file,
                )
                continue
            if skill.name in self.skills:
                log.warning(
                    "Duplicate skill name '%s' in %s; replacing previous",
                    skill.name,
                    skill_file,
                )
            self.skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def catalog_text(self) -> str:
        if not self.skills:
            return ""
        lines = ["Available skills:"]
        for skill in self.skills.values():
            lines.append(f"- {skill.name}: {skill.description}")
        lines.append("")
        lines.append(
            'If a skill applies to the user\'s request, start your response '
            'with {"skill": "name"} on its own line.'
        )
        lines.append(
            "Once a skill is active, its instructions remain in effect "
            "for the rest of the session."
        )
        return "\n".join(lines)

    @staticmethod
    def _parse(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        match = re.match(
            r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z",
            text,
            re.DOTALL,
        )
        if not match:
            raise ValueError("SKILL.md missing YAML frontmatter")
        front, body = match.group(1), match.group(2)
        meta: dict[str, str] = {}
        for line in front.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
        if "name" not in meta or "description" not in meta:
            raise ValueError(
                "SKILL.md frontmatter must contain name and description"
            )
        return Skill(
            name=meta["name"],
            description=meta["description"],
            body=body.strip(),
            path=path,
        )
```

### Step 4: Run tests to verify they pass

Run: `python -m pytest tests/test_skills.py -v`
Expected: All 7 tests PASS.

### Step 5: Leave work uncommitted

**Do NOT run `git commit`.** The user is committing themselves. Just leave the new and modified files in the working tree.
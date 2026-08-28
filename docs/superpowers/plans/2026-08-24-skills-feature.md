# Skills Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Anthropic-style Skills feature to `mini_agent`: markdown files in a top-level `skills/` directory that the LLM can activate by emitting `{"skill": "name"}` as the first line of a response; the activated skill's body is then appended to the system prompt for the rest of the session, available to both `--engine loop` and `--engine graph`.

**Architecture:** A new `SkillRegistry` parses `skills/<name>/SKILL.md` files (YAML frontmatter + markdown body). The existing `ContextProvider.build()` becomes the single funnel that:
1. Injects the skill catalog into the system prompt
2. Inspects the latest assistant message in retrieved history for a `{"skill": "name"}` first line
3. Persists the active skill across turns by reading the session's `_active_skill_name`
4. Appends the active skill's body to the system prompt

`AgentLoop` and `GraphAgent.ThinkNode` drop their own `self.system_prompt` prepending — `ContextProvider` owns the system message now.

**Tech Stack:** Python 3.11+, pytest. No new third-party deps.

**Spec:** `docs/superpowers/specs/2026-08-24-skills-feature-design.md`

---

## Global Constraints

- Python ≥ 3.11 (existing floor; verified in `pyproject.toml`).
- No new third-party dependencies — Skills uses Python's built-in `re`, `pathlib`, and standard `logging`.
- All existing tests must continue to pass: `tests/test_graph_agent.py`, `tests/test_graph_executor.py`, `tests/test_react_graph.py`, `tests/test_retrieval.py`.
- TDD: every code task writes its failing test first, then implementation, then commits.
- Commit messages follow the existing repo style: `<scope>: <change>` (e.g., `feat:`, `docs:`, `test:`, `fix:`).
- Skill `name` must match its directory name (kebab-case); validated at load time.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `mini_agent/skills.py` | **Create** | `Skill` dataclass; `SkillRegistry` (load, get, catalog_text) |
| `mini_agent/context.py` | **Modify** | Inject catalog + active skill into system message; detect `{"skill": ...}` prefix |
| `mini_agent/agent_loop.py` | **Modify** | Drop `self.system_prompt` prepending; rely on `ContextProvider` for system message |
| `mini_agent/graph_agent.py` | **Modify** | Same change in `ThinkNode.execute()` |
| `mini_agent/main.py` | **Modify** | Pass `system_prompt=SYSTEM` to `ContextProvider` |
| `skills/sample/SKILL.md` | **Create** | Sample skill so the catalog is non-empty on first run |
| `tests/test_skills.py` | **Create** | Tests for `SkillRegistry` + `ContextProvider` skill integration |

`SkillRegistry` is independent and can be built/tested first. `ContextProvider` depends on it. The engine changes depend on `ContextProvider` owning the system message.

---

## Task 1: `Skill` and `SkillRegistry`

**Files:**
- Create: `mini_agent/skills.py`
- Test: `tests/test_skills.py`

**Interfaces:**
- Produces: `Skill(name: str, description: str, body: str, path: Path)` and `SkillRegistry(skills_dir: Path) → SkillRegistry`
- `SkillRegistry.skills: dict[str, Skill]`
- `SkillRegistry.get(name) → Skill | None`
- `SkillRegistry.catalog_text() → str`

- [ ] **Step 1: Write failing tests for `SkillRegistry` parsing and catalog**

Create `tests/test_skills.py`:

```python
"""Tests for SkillRegistry and Skill SKILL.md parsing."""

import logging
import textwrap
from pathlib import Path

import pytest


# A reusable minimal SKILL.md body for tests.
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

    # No frontmatter at all.
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

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skills.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'mini_agent.skills'`.

- [ ] **Step 3: Implement `Skill` and `SkillRegistry`**

Create `mini_agent/skills.py`:

```python
"""Skills registry.

A skills is a folder under `skills_dir/<kebab-name>/SKILL.md` containing
YAML frontmatter (`name`, `description`) and a markdown body.

The agent injects the catalog into its system prompt and activates a
skills when the LLM emits `{"skill": "<name>"}` as the first line of
a response. The activated skills's body is then appended to the system
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add mini_agent/skills.py tests/test_skills.py
git commit -m "feat(skills): add SkillRegistry for SKILL.md parsing"
```

---

## Task 2: `ContextProvider` skill wiring

**Files:**
- Modify: `mini_agent/context.py`
- Test: `tests/test_skills.py` (extend)

**Interfaces:**
- Consumes: `SkillRegistry` (from Task 1)
- `ContextProvider(skills_dir: Path = Path("skills"))` — new parameter
- `ContextProvider.build(user_input) → AgentContext` — system message now embedded in result
- `ContextProvider._active_skill_name: str | None` — set when intent detected
- `AgentContext.skill_intent: str | None` — new field (optional)

- [ ] **Step 1: Write failing tests for `ContextProvider` skill integration**

Append to `tests/test_skills.py`:

```python
import types
from pathlib import Path


class _FakeSession:
    """Stand-in for mini_agent.session.Session used by ContextProvider."""
    def __init__(self, session_id="test-session"):
        self.session_id = session_id


class _FakeRetriever:
    """Returns the messages as-is, no real retrieval."""
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
    # No system message injected at all.
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

    # Retriever returns different messages on successive calls.
    class _MultiTurnRetriever:
        def __init__(self):
            self.call_count = 0

        def retrieve(self, session, query):
            self.call_count += 1
            if self.call_count == 1:
                return [
                    {"role": "user", "content": "review my PR"},
                    {
                        "role": "assistant",
                        "content": '{"skill": "review-pr"}\ngo',
                    },
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

    # Second turn: no skill intent in history; skill must persist.
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
            {
                "role": "assistant",
                "content": '{not valid json at all',
            },
        ]),
        skill_registry=reg,
    )

    ctx = provider.build("hi")
    system = ctx.messages[0]
    assert "# Active skill:" not in system["content"]
```

> Note: the persistence test uses a `_MultiTurnRetriever` whose return changes between calls — no monkey-patching needed.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skills.py -v -k "context_"`
Expected: All 6 `context_*` tests FAIL (the new behavior isn't implemented yet).

- [ ] **Step 3: Modify `ContextProvider` to inject skill catalog and active skill**

Replace `mini_agent/context.py` with:

```python
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .skills import SkillRegistry

SKILL_INTENT_RE = re.compile(
    r'\A\s*\{"skill":\s*"([^"]+)"\}\s*(?:\n|\Z)'
)


@dataclass
class AgentContext:
    messages: list[Any] = field(default_factory=list)
    skill_intent: str | None = None


class ContextProvider:

    def __init__(
        self,
        session,
        retriever,
        skills_dir: Path | None = None,
        skill_registry: SkillRegistry | None = None,
    ):
        self.session = session
        self.retriever = retriever
        if skill_registry is not None:
            self.skills = skill_registry
        else:
            self.skills = SkillRegistry(skills_dir or Path("skills"))
        self._active_skill_name: str | None = None

    def build(self, user_input: str) -> AgentContext:
        messages = self._retrieve_messages(user_input)
        self._maybe_activate_from_history(messages)

        system = self._build_system_message()
        if system is not None:
            messages = [system, *messages]

        return AgentContext(messages=messages)

    # Internal helpers ---------------------------------------------------

    def _retrieve_messages(self, user_input: str) -> list[dict]:
        return self.retriever.retrieve(self.session, user_input)

    def _maybe_activate_from_history(self, messages: list[dict]) -> None:
        for m in reversed(messages):
            if m.get("role") == "assistant":
                content = m.get("content") or ""
                first_line = content.split("\n", 1)[0]
                match = SKILL_INTENT_RE.match(first_line)
                if match:
                    name = match.group(1)
                    if self.skills.get(name) is not None:
                        self._active_skill_name = name
                return

    def _build_system_message(self) -> dict | None:
        parts: list[str] = []
        catalog = self.skills.catalog_text()
        if catalog:
            parts.append(catalog)
        if self._active_skill_name:
            skill = self.skills.get(self._active_skill_name)
            if skill is not None:
                parts.append(f"# Active skill: {skill.name}\n{skill.body}")
        if not parts:
            return None
        return {"role": "system", "content": "\n\n".join(parts)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skills.py -v`
Expected: All 13 tests PASS (7 registry + 6 context).

- [ ] **Step 5: Run full suite to confirm no regressions**

Run: `python -m pytest tests/ --ignore=tests/test_conditional_graph_routing.py -v`
Expected: All pre-existing tests still PASS (the Fakes in `test_graph_agent.py` don't go through real `ContextProvider`, so they're unaffected by the new `skill_registry` parameter).

- [ ] **Step 6: Commit**

```bash
git add mini_agent/context.py tests/test_skills.py
git commit -m "feat(skills): inject skill catalog and active skill into system message"
```

---

## Task 3: Drop redundant `system_prompt` prepending in engines

**Files:**
- Modify: `mini_agent/agent_loop.py` (1 line in `run()`)
- Modify: `mini_agent/graph_agent.py` (1 line in `ThinkNode.execute()`)

**Interfaces:**
- Consumes: `ContextProvider.build()` now returns `messages` whose first element is the system message
- `AgentLoop.system_prompt` — REMOVE
- `GraphAgent.system_prompt` — REMOVE (only used to prepend; no other consumer)

- [ ] **Step 1: Update `AgentLoop.run()`**

In `mini_agent/agent_loop.py`, locate the block:

```python
        messages = [
            self.system_prompt,
            *context.messages,
        ]
```

Replace with:

```python
        messages = context.messages
```

Then locate the `__init__` signature and remove the `system_prompt` parameter and the `self.system_prompt = ...` assignment. The block to remove:

```python
            system_prompt=None,
            ):
        ...
        self.system_prompt = {
            "role": "system",
            "content": system_prompt
        }
```

becomes:

```python
            ):
```

(keeping only the `)` at the end of `__init__`'s parameter list and the closing of `__init__`'s body).

- [ ] **Step 2: Update `GraphAgent.ThinkNode.execute()`**

In `mini_agent/graph_agent.py`, locate:

```python
        messages = [self.system_prompt, *context.messages]
```

Replace with:

```python
        messages = context.messages
```

Then remove the `system_prompt` parameter from `GraphAgent.__init__` and the corresponding attribute assignment. The block:

```python
            event_factory=None,
            system_prompt=None,
    ):
        ...
        self.system_prompt = (
            {"role": "system", "content": system_prompt}
            if system_prompt
            else {"role": "system", "content": self.DEFAULT_SYSTEM_PROMPT}
        )
```

becomes:

```python
            event_factory=None,
    ):
```

and remove the `self.system_prompt = ...` lines.

Also remove `DEFAULT_SYSTEM_PROMPT` class attribute — no longer used.

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ --ignore=tests/test_conditional_graph_routing.py -v`
Expected: All 13 + pre-existing tests PASS.

If any pre-existing test fails because it expected `self.system_prompt` to exist (none should — `test_graph_agent.py` uses `FakeContextProvider` which doesn't depend on the real one), update those tests to drop the assertion.

- [ ] **Step 4: Commit**

```bash
git add mini_agent/agent_loop.py mini_agent/graph_agent.py
git commit -m "refactor: drop redundant system_prompt prepending (ContextProvider owns it)"
```

---

## Task 4: Wire default `system_prompt` into `ContextProvider` via `main.py`

**Files:**
- Modify: `mini_agent/main.py`

**Interfaces:**
- `ContextProvider(system_prompt=...)` — accept a default prompt body (optional)

- [ ] **Step 1: Add `system_prompt` parameter to `ContextProvider.__init__`**

In `mini_agent/context.py`, add `system_prompt` to `ContextProvider.__init__`:

```python
    def __init__(
        self,
        session,
        retriever,
        skills_dir: Path | None = None,
        skill_registry: SkillRegistry | None = None,
        system_prompt: str | None = None,
    ):
        self.session = session
        self.retriever = retriever
        if skill_registry is not None:
            self.skills = skill_registry
        else:
            self.skills = SkillRegistry(skills_dir or Path("skills"))
        self._default_system_prompt = system_prompt
        self._active_skill_name: str | None = None
```

Update `_build_system_message()` to prepend the default prompt:

```python
    def _build_system_message(self) -> dict | None:
        parts: list[str] = []
        if self._default_system_prompt:
            parts.append(self._default_system_prompt)
        catalog = self.skills.catalog_text()
        if catalog:
            parts.append(catalog)
        if self._active_skill_name:
            skill = self.skills.get(self._active_skill_name)
            if skill is not None:
                parts.append(f"# Active skill: {skill.name}\n{skill.body}")
        if not parts:
            return None
        return {"role": "system", "content": "\n\n".join(parts)}
```

- [ ] **Step 2: Add a regression test for default prompt**

Append to `tests/test_skills.py`:

```python
def test_context_default_system_prompt_is_first(skills_dir):
    from mini_agent.context import ContextProvider
    from mini_agent.skills import SkillRegistry

    reg = SkillRegistry(skills_dir=skills_dir)  # empty
    provider = ContextProvider(
        session=_FakeSession(),
        retriever=_FakeRetriever([
            {"role": "user", "content": "hi"},
        ]),
        skill_registry=reg,
        system_prompt="You are a helpful assistant.",
    )

    ctx = provider.build("hi")
    assert ctx.messages[0] == {
        "role": "system",
        "content": "You are a helpful assistant.",
    }
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_skills.py -v`
Expected: All tests PASS (14 total now).

- [ ] **Step 4: Update `main.py` to construct `ContextProvider` with `system_prompt=SYSTEM`**

In `mini_agent/main.py`, locate:

```python
    context_providor = ContextProvider(session=session, retriever=retriever)
```

Replace with:

```python
    context_providor = ContextProvider(
        session=session,
        retriever=retriever,
        system_prompt=SYSTEM,
    )
```

Also remove `system_prompt=SYSTEM` from the `Agent(...)` and `GraphAgent(...)` constructors (it's no longer a parameter on either engine — see Task 3).

The `common_kwargs` dict in `main.py` should become:

```python
    common_kwargs = dict(
        context_provider=context_providor,
        model_client=model_client,
        tool_executor=tool_executor,
        registry=registry,
        message_store=message_store,
        event_bus=event_bus,
        event_factory=event_factory,
    )

    if args.engine == "loop":
        agent = Agent(**common_kwargs, session=session)
    else:
        agent = GraphAgent(**common_kwargs)
```

- [ ] **Step 5: Verify imports still work**

Run: `python -c "from mini_agent.main import main; from mini_agent.context import ContextProvider; print('imports OK')"`
Expected: prints `imports OK`.

- [ ] **Step 6: Commit**

```bash
git add mini_agent/context.py mini_agent/main.py tests/test_skills.py
git commit -m "feat(skills): wire default system prompt into ContextProvider"
```

---

## Task 5: Sample skill

**Files:**
- Create: `skills/sample/SKILL.md`

**Interfaces:** None (data only).

- [ ] **Step 1: Create the sample skill**

```bash
mkdir -p skills/sample
```

Create `skills/sample/SKILL.md`:

```markdown
---
name: sample
description: A sample skill that demonstrates the format. Use it as a template for new skills.
---

# Sample Skill

This is a starter skill showing the structure. Replace this body with real instructions.

When activated, follow these steps:
1. Acknowledge the skill is active
2. Apply its guidance to the user's request
3. Stay in this mode for the rest of the session
```

- [ ] **Step 2: Verify the catalog includes it**

Run: `python -c "
from mini_agent.skills import SkillRegistry
reg = SkillRegistry()
print(reg.catalog_text())
print('skills:', list(reg.skills.keys()))
"`
Expected: catalog text contains `- sample: A sample skill...`, skills list includes `'sample'`.

- [ ] **Step 3: Commit**

```bash
git add skills/sample/SKILL.md
git commit -m "docs(skills): add sample SKILL.md template"
```

---

## Task 6: End-to-end verification

**Files:** None.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ --ignore=tests/test_conditional_graph_routing.py -v`
Expected: ALL tests PASS (14 in `test_skills.py` + 8 pre-existing).

- [ ] **Step 2: Smoke-test both engines import cleanly**

Run: `python -m mini_agent.main --help`
Expected: argparse `--engine {loop,graph}` help message renders, no import errors.

- [ ] **Step 3: Update `graph/graph_explain.md` to mention Skills**

Append to `graph/graph_explain.md` (under a new section or in §8 "What lives outside the graph"):

> `mini_agent/skills.py` — markdown-only Skills feature: parses `skills/<name>/SKILL.md` files; the catalog is injected into the system prompt via `ContextProvider`. The LLM activates a skill by emitting `{"skill": "name"}` on the first line of its response; the active skill's body then stays in context for the rest of the session.

Also update `mini_agent/context.py` documentation if there's a docstring section.

- [ ] **Step 4: Commit (if any doc updates were made)**

```bash
git add graph/graph_explain.md
git commit -m "docs(graph): note Skills integration with ContextProvider"
```

---

## Acceptance Criteria

- [ ] All 6 tasks completed.
- [ ] Full test suite passes: ≥14 tests in `test_skills.py` + 8 pre-existing = ≥22 PASS.
- [ ] `uv run mini-agent --engine loop --help` works (no import errors).
- [ ] `uv run mini-agent --engine graph --help` works.
- [ ] With `skills/sample/SKILL.md` present, asking the LLM to "show me the sample skill" (or any phrasing that matches its description) causes the LLM to emit `{"skill": "sample"}` as the first line of its response.
- [ ] Subsequent turns continue to see the active skill's body in the system prompt (verifiable by adding a debug print in `_build_system_message` if needed).
- [ ] No regression in the existing calculator/time/notes tools.

## Out of Scope (deferred)

- Per-skill tool overrides
- Skill scripts/executables
- Skill deactivation (only switching is supported in v1)
- Skill versioning, signing, marketplace
- Hot-reload of skills at runtime (registry loads once at `ContextProvider.__init__`)
# Skills Feature — Design Spec

**Date:** 2026-08-24
**Status:** Draft
**Author:** (brainstormed with user)

## Purpose

Add an **Anthropic-style Skills feature** to `mini_agent`: a way to author procedural knowledge in markdown, expose it to the LLM as a catalog, and have the LLM activate the relevant skill's instructions for the rest of the session.

This lets the user (or future contributors) encode domain-specific workflows — code review, meeting scheduling, research summarization — as plain markdown files, without writing Python. The agent gains the ability to follow multi-step procedures authored declaratively.

## Goals

1. **Markdown-only.** Skills are `.md` files with YAML frontmatter. No code, no scripts. (YAGNI.)
2. **Zero new abstractions for users.** Skills are *not* tools, not sub-agents, not callable functions. They are *instructions the LLM reads*.
3. **Both engines.** `--engine loop` and `--engine graph` both honor skills.
4. **Persistent activation.** Once a skill is active, its body stays in context for the rest of the session.
5. **Discovery via filesystem.** Skills live in a top-level `skills/` directory. Adding a folder = adding a skill. No registration step.

## Non-Goals

- Scripts/executables inside skill folders (deferred — YAGNI).
- Per-skill tools or tool overrides (deferred — YAGNI).
- Skill marketplace, versioning, signing (deferred).
- UI for browsing installed skills (deferred).
- Mid-session skill *un*loading (switching is allowed; full deactivation is not).

## Concepts

### Skill

A single skill is a directory containing one `SKILL.md` file:

```
skills/
└── review-pr/
    └── SKILL.md
```

`SKILL.md` has two parts:

1. **YAML frontmatter** (between `---` lines) with exactly two keys:
   - `name` — kebab-case identifier matching the directory name (validated).
   - `description` — one short sentence. Injected into the system prompt so the LLM knows when to pick this skill.
2. **Markdown body** — the procedural instructions. Anything after the closing `---`.

Example `skills/review-pr/SKILL.md`:

```markdown
---
name: review-pr
description: Review a pull request by examining code quality, tests, and architecture.
---

# Review PR

When the user asks you to review a PR:
1. Fetch the diff via `git diff main...HEAD`
2. ...
```

### Skill catalog

At agent startup, the system scans `skills/` and produces a `(name, description)` list for every well-formed skill. This list is rendered into the system prompt as:

```
Available skills:
- review-pr: Review a pull request by examining code quality, tests, and architecture.
- schedule-meeting: Schedule a meeting by checking calendars and proposing times.

If a skill applies to the user's request, start your response with {"skill": "name"} on its own line.
Once a skill is active, its instructions remain in effect for the rest of the session.
```

If no skills are present, the catalog block is omitted entirely (no empty section).

### Activation signal

The LLM signals skill selection by emitting a JSON line as the **first line** of its response:

```
{"skill": "review-pr"}
<reasoning or normal answer>
```

The first line is checked by `ContextProvider._extract_skill_intent()` after each LLM call. If the first line is exactly `{"skill": "<name>"}`, the named skill is activated.

If the first line is malformed JSON, or names an unknown skill, it is treated as **content** (the LLM just happened to start with that text). No error is raised.

### Active skill in context

Once a skill is active, every subsequent `ContextProvider.build()` returns a `messages` list whose first message (after `system`) contains:

```
<original system prompt>

# Active skill: review-pr
<skill body>
```

This is the persistence mechanism. Both engines construct their messages via `ContextProvider.build()`, so both engines inherit the active skill automatically.

To switch skills, the LLM emits a new `{"skill": "new_name"}` line in a later turn. There is no explicit deactivation in v1.

## Architecture

### New file: `mini_agent/skills.py`

```python
from pathlib import Path
import re
import logging

log = logging.getLogger(__name__)

class Skill:
    name: str
    description: str
    body: str
    path: Path

class SkillRegistry:
    """Loads and queries skills from a skills/ directory."""

    def __init__(self, skills_dir: Path = Path("skills")):
        self.skills_dir = Path(skills_dir)
        self.skills: dict[str, Skill] = {}
        self.load_all()

    def load_all(self) -> None:
        """Scan skills_dir/<name>/SKILL.md and parse each. Idempotent."""
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
                if skill.name != entry.name:
                    log.warning(
                        "Skill name '%s' does not match directory '%s' (%s); skipping",
                        skill.name, entry.name, skill_file,
                    )
                    continue
                self.skills[skill.name] = skill
            except Exception as e:
                log.warning("Failed to load skill from %s: %s", skill_file, e)

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def catalog_text(self) -> str:
        """Format as 'Available skills:\n- name: description\n...' or '' if empty."""
        if not self.skills:
            return ""
        lines = ["Available skills:"]
        for skill in self.skills.values():
            lines.append(f"- {skill.name}: {skill.description}")
        lines.append("")
        lines.append(
            'If a skill applies to the user\'s request, start your response with '
            '{"skill": "name"} on its own line.'
        )
        lines.append(
            "Once a skill is active, its instructions remain in effect for the rest of the session."
        )
        return "\n".join(lines)

    @staticmethod
    def _parse(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        m = re.match(
            r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z",
            text,
            re.DOTALL,
        )
        if not m:
            raise ValueError("SKILL.md missing YAML frontmatter")
        front, body = m.group(1), m.group(2)
        # Minimal frontmatter parser — supports `name:` and `description:` only.
        meta = {}
        for line in front.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
        if "name" not in meta or "description" not in meta:
            raise ValueError("SKILL.md frontmatter must contain name and description")
        return Skill(
            name=meta["name"],
            description=meta["description"],
            body=body.strip(),
            path=path,
        )
```

### Modified file: `mini_agent/context.py`

```python
import json
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from .skills import SkillRegistry

@dataclass
class AgentContext:
    messages: list[Any]
    skill_intent: str | None = None  # NEW: name from {"skill": "..."} prefix, if any

class ContextProvider:
    SKILL_INTENT_RE = re.compile(r'\A\s*\{"skill":\s*"([^"]+)"\}\s*(?:\n|\Z)')

    def __init__(self, session, retriever, skills_dir: Path = Path("skills")):
        self.session = session
        self.retriever = retriever
        self.skills = SkillRegistry(skills_dir)
        # Active skill lives on the session so it survives across turns.
        self._active_skill_name: str | None = None

    def build(self, user_input: str) -> AgentContext:
        messages = self.retriever.retrieve(self.session, user_input)

        # Find the latest assistant message in retrieved history.
        # If its first line is a skill-intent JSON, activate the named skill.
        for m in reversed(messages):
            if m.get("role") == "assistant":
                first_line = (m.get("content") or "").split("\n", 1)[0]
                match = self.SKILL_INTENT_RE.match(first_line)
                if match:
                    self._activate(match.group(1))
                break

        # Inject active skill body into system prompt.
        system_block = self._build_system_block()
        if system_block:
            messages = [system_block, *messages]

        return AgentContext(messages=messages)

    def _activate(self, name: str) -> None:
        skill = self.skills.get(name)
        if skill is not None:
            self._active_skill_name = name

    def _build_system_block(self) -> dict | None:
        parts = []
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

**Important behavior change:** `ContextProvider.build()` previously returned messages that the caller prepended a system prompt to (see `AgentLoop` and `ThinkNode`). With this change, the system prompt (with skill catalog and active skill) is now built *inside* `build()`. Callers no longer prepend a system prompt of their own — the system message comes from the context.

This requires a coordinated change in both engines:

- `AgentLoop.run()` (line ~84): remove `self.system_prompt` from the messages list; rely on `ContextProvider.build()` to provide the system message.
- `mini_agent/graph_agent.py` `ThinkNode.execute()` (line ~71): remove `messages = [self.system_prompt, *context.messages]`; use `context.messages` directly.

### Unchanged files

- `mini_agent/agent.py` — passes deps into `AgentLoop`; no skill-specific changes.
- `mini_agent/main.py` — `SYSTEM` constant is removed (or repurposed as the default prompt body inside `ContextProvider`).
- `mini_agent/agent_loop.py` — only the one-line change above.
- `mini_agent/graph_agent.py` — only the one-line change above.
- `mini_agent/tools/`, `mini_agent/llm/` — untouched.

### Default system prompt

The default agent prompt (currently in `mini_agent/main.py` and `mini_agent/agent.py`) becomes the default body of a `_default_system_prompt` accessible by `ContextProvider` (e.g., passed in via `__init__`). For backward compatibility, if no system prompt is configured, `ContextProvider` still injects one.

## Data flow

```
User: "review my latest PR"
│
│  1. AgentLoop.run() / GraphAgent.run()
│     self.message_store.add_user(...)
│
│  2. context_provider.build(user_input)
│     │
│     ├─ Retrieve prior messages (recent + relevant from memory.db)
│     ├─ Find latest assistant message; check first line for {"skill": "..."}
│     ├─ If found and valid, activate that skill in self._active_skill_name
│     ├─ Build system message:
│     │     catalog_text()   (if skills exist)
│     │     + active skill body (if active)
│     └─ Return AgentContext(messages=[system, ...retrieved])
│
│  3. model_client.generate(messages, tools)
│     LLM sees:
│       system: "Available skills:\n- review-pr: ...\n..."
│       user: "review my latest PR"
│       tools: [...]
│     LLM responds with:
│       {"skill": "review-pr"}
│       I'll start by fetching the diff...
│
│  4. ContextProvider activated skill on next build.
│     Subsequent calls see:
│       system: "Available skills:\n...\n\n# Active skill: review-pr\n[body]"
│
│  5. Loop continues until the LLM returns a non-tool-call response.
```

## Error handling

| Scenario | Behavior |
|---|---|
| `skills/` directory missing | `SkillRegistry.load_all()` returns early; `catalog_text()` returns `""`. No error. |
| `skills/foo/SKILL.md` malformed | Logged warning; skill is skipped. Other skills still load. |
| `SKILL.md` frontmatter `name` ≠ directory name | Logged warning; skill skipped. |
| Two skills with the same `name` | Last one wins; warning logged. |
| LLM emits `{"skill": "unknown"}` | Unknown → no-op. Skill stays whatever it was (or None). |
| LLM emits malformed JSON on first line | Treated as content; no skill activated. |
| LLM emits `{"skill": "x"}` mid-response (not first line) | Ignored — only the first line is checked. |

## Testing strategy

New file: `tests/test_skills.py`

| Test | Asserts |
|---|---|
| `test_registry_loads_valid_skill` | Given a tempdir with `skills/review-pr/SKILL.md`, registry has the skill with correct name/description/body. |
| `test_registry_skips_malformed` | Given a tempdir with a malformed SKILL.md, that skill is skipped and a warning is logged. |
| `test_registry_name_must_match_dir` | Skill with `name: foo` in dir `bar/` is skipped. |
| `test_catalog_text_format` | `catalog_text()` matches the documented format. |
| `test_catalog_text_empty_when_no_skills` | `catalog_text()` returns `""` when registry is empty. |
| `test_context_activates_skill_from_intent` | After an assistant message with first line `{"skill": "review-pr"}`, `build()` returns messages whose system contains the skill body. |
| `test_context_persists_skill_across_turns` | After activation, subsequent `build()` calls include the skill body in system. |
| `test_context_unknown_skill_ignored` | `{"skill": "unknown"}` doesn't raise; no skill activated. |
| `test_context_malformed_json_ignored` | First line that's not valid JSON intent is treated as content. |

Existing tests in `tests/test_graph_agent.py`, `tests/test_graph_executor.py`, `tests/test_react_graph.py`, `tests/test_retrieval.py` should continue to pass with no modifications (they use fakes and don't depend on `ContextProvider.build()`'s output shape, except where the system prompt changes are noted).

The two changes that *will* break tests:
- `AgentLoop` no longer prepends its own `self.system_prompt` to messages — but no existing test asserts on the system prompt directly.
- `ThinkNode` no longer prepends `self.system_prompt` — same.

If any test fails because of the system-prompt change, the fix is to make the test construct an `AgentContext` whose `messages` already contain the system block, mirroring production behavior.

## Migration plan

1. **Add `mini_agent/skills.py`** (new). No existing code changed.
2. **Update `mini_agent/context.py`** to construct the system message.
3. **Update `mini_agent/agent_loop.py`** and `mini_agent/graph_agent.py`** to drop the now-redundant `system_prompt` prepending.
4. **Update `mini_agent/main.py`** to pass the default system prompt into `ContextProvider`.
5. **Add a sample skill** (`skills/sample/SKILL.md`) so the catalog isn't empty on first run.
6. **Add `tests/test_skills.py`** with the cases above.
7. **Run full test suite.** Expect existing tests to pass without modification.

## Open questions

None at design time. All major decisions resolved in brainstorm:

- ✅ Markdown only (YAGNI).
- ✅ Top-level `skills/` directory.
- ✅ Auto-detected, not a tool.
- ✅ Persistent activation.
- ✅ Both engines.

## Acceptance criteria

- [ ] `tests/test_skills.py` passes (≥9 cases).
- [ ] All pre-existing tests still pass.
- [ ] `uv run mini-agent --engine loop` and `uv run mini-agent --engine graph` both work.
- [ ] With a skill installed (e.g., `skills/review-pr/SKILL.md`), asking the LLM to "review this PR" causes the LLM to emit `{"skill": "review-pr"}` and follow the skill's instructions.
- [ ] Once activated, the skill body remains visible in subsequent system prompts (verifiable via trace events or by adding a debug print).
- [ ] No regression in the calculator/time tools.

## Out of scope (deferred)

- Per-skill tool overrides
- Skill scripts/executables
- Skill deactivation (only switching is supported)
- Skill versioning, signing, marketplace
- Hot-reload of skills at runtime (registry loads once at startup)
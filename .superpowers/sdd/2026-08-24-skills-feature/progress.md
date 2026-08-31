# SDD ledger — plan: docs/superpowers/plans/2026-08-24-skills-feature.md

**Branch:** main (per user's established pattern in this session; explicit "approve, go ahead" consent given).
**Spec:** docs/superpowers/specs/2026-08-24-skills-feature-design.md
**Workspace:** .superpowers/sdd/2026-08-24-skills-feature/

---

## Pre-flight review

Scanning the plan for self-inconsistencies and conflicts against the spec.

| Pair / Check | What I checked | Finding |
|---|---|---|
| Task 1 → Task 2 | `SkillRegistry` consumed by `ContextProvider` | OK — Task 1 produces `Skill` dataclass + `SkillRegistry`, Task 2 imports it. Types align. |
| Task 2 → Task 3 | `ContextProvider.build()` returns messages-with-system; engines drop their own prepending | OK — Task 3 removes `messages = [self.system_prompt, *context.messages]` in both engines. Aligns with spec. |
| Task 4 vs Task 3 | Task 4 modifies `ContextProvider.__init__` to add `system_prompt`; Task 3 already removed the engine's `system_prompt` parameter | OK — Task 4's `ContextProvider` change doesn't reintroduce the engine-side `system_prompt`. main.py drop is covered. |
| Spec regex `\A\s*\{"skill":\s*"([^"]+)"\}\s*(?:\n|\Z)` vs Task 2 implementation | Implementation uses the same regex | OK |
| Global constraints vs Task 1 test that imports `mini_agent.skills` | Tests assume the module path is `mini_agent.skills` | OK — Task 1 creates it at that path |
| Tests vs `Skill` dataclass fields | Tests access `skill.name`, `skill.description`, `skill.body` | OK — all four fields defined in dataclass |
| `test_context_persists_skill_across_turns` uses `_MultiTurnRetriever` | Verified the test pattern is sound; clean, no monkey-patching | OK |
| Task 6 Step 3 graph_explain.md update | Adding a one-line note about Skills | OK — doc was already updated earlier this session for graph changes |

**Pre-flight scan: clean.** No conflicts found.

---

## Rulings

(none yet)

---

## Task completions

(none yet)

---

## Status (2026-08-24)

**Resuming implementation.** User asked to continue with Skills feature.

### Rulings

**Ruling 1 — No implementer commits.** User stated: "do not commit I'll commit myself for myself in this project." From this point forward:
- Implementer subagents MUST NOT run `git commit`. Their final step is "leave work uncommitted in working tree".
- Reviewers still run `git diff` against BASE for review purposes.
- Task review-packages still use `scripts/review-package PLAN_FILE BASE HEAD` — but since commits don't happen, BASE = HEAD before each implementer starts (already what the skill prescribes).
- "What it costs if wrong": user wanted commit granularity they control; if I commit anyway I'm doing work they explicitly said not to do. Undoing a commit is messy (force-amend/revert), which costs them time.
- **Cost-of-reversal:** trivial — just don't `git add`/`git commit`. No downside.

The plan's per-task "Step N: Commit" is replaced with "leave changes uncommitted in working tree".

---

## Status (2026-08-24) — resumed

Resuming at Task 1. Working tree state:
- `mini_agent/skills.py` exists but is empty (0 bytes) — Task 1 will fill it.
- `mini_agent/main.py` has been modified by the user to register a `GetYfTool` (their yfinance tool work — unrelated to Skills).
- `pyproject.toml` has `yfinance>1.1` added.
- These untracked/modified files are the user's work and are not part of the Skills plan.

---

## Status (2026-08-24) — switched to teaching mode

User instruction: "do not write code. teach me how on each step."

Aborting subagent-driven execution. From this point:
- I will not dispatch implementer subagents
- I will not write code blocks for the user
- I will explain what each step does, what files to touch, what to write, and why
- User writes the code themselves
- I review what they wrote and answer questions

Task 1 has already been implemented by a subagent (uncommitted in working tree, 7/7 tests passing). User can inspect `mini_agent/skills.py` and `tests/test_skills.py` to see one reference implementation.

For Tasks 2-6, I teach; user writes; user commits.
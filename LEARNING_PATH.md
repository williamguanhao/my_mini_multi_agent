# mini_multi_agent — Learning Path

This project upgrades from single agent to graph and multi agent.
Given real tool, it can handle financial research, pricing ect.

The full improvement plan lives in [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Foundation hardening (2026-09-13, done before Phase 4)

Why before Phase 4: you cannot build "agent as node" on a base where dead code
contradicts the live interfaces and nothing guards regressions. What changed and why:

- **`.env` untracked + `.env.example`** — secrets in git history are unrecoverable by
  deleting the file later; `.gitignore` only prevents *future* tracking. Lesson: rotate
  keys that ever touch history.
- **Dead code deleted** (`graph/runner.py`, `graph/agent_graph.py`, old `graph/nodes/*`,
  stale eval entry points) — it referenced interfaces that never existed
  (`agent.complete(state)`), which misleads every future "agent as node" attempt.
  Lesson: production repos tolerate no parallel truths.
- **Three real bugs fixed**: `state.error = error,` made a tuple (`agent_loop.py`);
  `GraphExecutor` crashed on `max_steps=None` because the loop used the parameter
  instead of `step_limit`; `node_started` events embedded a live `GraphState` object,
  which is not JSON-serializable — any JSON trace sink would have failed.
- **`print` → `logging`** — prints can't be filtered by level or routed per handler;
  module-level `logging.getLogger(__name__)` is the standard seam.
- **uv workspace + dev group + CI** — `fredapi`/`ddgs`/`pytest` now live in
  `uv.lock` (reproducible), and GitHub Actions runs ruff + pytest with empty credentials,
  forcing tests to stay fake-based.

### Follow-up fix: web search returned nothing (2026-09-13)

The `web_search` tool answered every query with "No results". Root cause chain:
the `duckduckgo_search` package was **renamed to `ddgs`** and its old DuckDuckGo
backend stopped returning data — the library didn't crash, it silently returned
zero rows, so the failure surfaced only as the LLM saying "search isn't working".
Lessons:

1. A tool that *fails silently* is worse than one that raises — the agent can't
   distinguish "no results exist" from "the tool is broken". Error messages should
   say which.
2. Pin deps to maintained packages. `duckduckgo-search` is abandoned upstream;
   migrated to `ddgs>=9` (same `title`/`href`/`body` result shape).
3. While verifying end-to-end through `MCPClient`, confirmed the known shutdown
   wart: anyio cancel scopes can't be exited from a different asyncio task than
   they entered — `BackgroundLoop.run()` spawns one task per call. `disconnect()`
   is now best-effort with a warning log; the real fix is roadmap #5
   (native-async MCP client).

---

## Phase 1 — Refactor the existing Agent Loop



## Phase 2 — Make tracing first-class



## Phase 3 — Build the Graph Engine



## Phase 4 — Agent as Graph Node

**Done 2026-09-13** — notebook: [`notebooks/01_agent_as_node.ipynb`](notebooks/01_agent_as_node.ipynb)

The idea: an "agent" stops being a mystical orchestrator and becomes just another
node in a graph — its entire job is *context → model → decision*. Everything else
(executing tools, finishing, routing) is a different node's job.

What made it click:

- **A node is only as smart as its inputs.** `AgentNode` receives a model client,
  a context provider, and a registry — it knows nothing about SQLite, MCP, or
  skills. Dependencies are injected; the graph is just wiring.
- **State is the API between nodes.** We defined five keys (`run_id`,
  `user_input`, `decision`, `tool_calls_log`, `final_output`) and the decision
  shape `{"type": "tool"|"answer", ...}`. Once the contract is explicit, nodes
  from different authors compose. Full typed channels (#2) is this idea taken further.
- **Identity in state, not in constructors** was the unlock: the same `AgentNode`
  instance now serves every run, so the graph is built once. Per-run rebuild was
  the smell that originally forced `run_id` into constructors.
- **Two event sources, one vocabulary**: the executor emits `node_*`/`edge_traversed`,
  nodes emit `model_*`/`tool_*`, the agent emits `run_*`. Trace output is engine-
  independent — the property the whole tracing phase was building toward.

Watch out for: don't let nodes mutate each other's keys silently — that is exactly
what typed state (#2) will make impossible.

## Phase 5 — Multi-Agent Runtime



## Phase 6 — Real Research Tools



## Phase 7 — Skills



## Phase 8 — Upgrade Memory + Eval



## Phase 9 — build financial research & pricing agent


# ROADMAP — evolving mini_agent toward a production agent framework

Reference model: [hermes-agent](https://github.com/NousResearch/hermes-agent) — we copy its
*patterns*, not its size. Guiding theme: **agent-as-node** — the `graph/` engine
(`Node`/`Edge`/`Router`/`GraphExecutor`) is the narrow waist; agents, tools, and subagents
are all nodes on it.

The foundation work below is done. The 10 improvements are the plan proper; each lands as a
small, testable increment with tests and a learning note in `LEARNING_PATH.md`.

---

## Foundation (done 2026-09-13 — not counted in the 10)

- Secrets hygiene: `.env` untracked, `.env.example` added (keys still in git history — **rotate
  MiniMax/FRED keys**).
- Dead code removed: `graph/runner.py`, `graph/agent_graph.py`, `graph/nodes/*` (rebuilt by #1),
  demo node stubs, stale eval entry points, `mini_agent/trace/replay.py`, unused dataclasses.
- Real bugs fixed: `agent_loop` error tuple, `GraphExecutor` step-limit crash, live-`GraphState`
  payload in `node_started` events (JSON-safety).
- `print` → `logging`; shared system prompt in `mini_agent/prompts.py`.
- Packaging: dev dependency group (pytest/ruff/mypy), uv workspace over the three MCP servers,
  `mcp<2` pin everywhere, `agent-eval` entry point working again.
- Tests: all files collect and pass (44); eval harness rebuilt on the current `Event` API and
  unit-tested with fakes; GitHub Actions CI (ruff + pytest, no credentials).

---

## Top-10 improvements

| # | Improvement | What & why | Hermes parallel | Phase |
|---|---|---|---|---|
| 1 | **Agent as Node — for real** | Rebuild `graph/nodes/` canonically: `AgentNode` wraps `ModelClient` + `ContextProvider` and writes a typed `decision` channel; `ToolNode` wraps `ToolExecutor`; `GraphAgent` becomes a thin builder over these nodes (its private Think/Act/Answer duplicates are deleted). Pass run context (`run_id`) at execute time instead of rebuilding the graph every run. | One `AIAgent` core, many surfaces; "narrow waist" | 4 |
| 2 | **Typed graph state** | Replace the untyped `values: dict[str, Any]` bag with channels + reducers (append semantics for lists like `tool_calls_log`, last-write for scalars). Makes fan-out safe later; turns `snapshot()` into a checkpoint primitive. | Prompt-cache-first / immutable-past discipline | 4 |
| 3 | **Model gateway: providers + reliability + streaming** | Collapse the three clone LLM clients into one OpenAI-compatible client + provider config; retries with backoff on 429/5xx, request timeouts; streaming path emitting token events through `EventBus`. | Provider resolver, error classification, fallback cooldown | — |
| 4 | **Checkpointing & resumability** | SQLite checkpointer persisting `GraphState.snapshot()` per (run_id, step); transactional per-step message writes (root-fixes the orphan-tool-call repair hack in `retrieval.py`); `resume()` API. | Session lifecycle, state-db recovery, crash resume | 5 |
| 5 | **Async & parallel execution** | Async `Node.execute` + async executor path; parallel tool calls with per-tool timeouts; native-async `MCPClient` (retire the `BackgroundLoop` thread hack); sync facade kept for the CLI. | Concurrent delegation, streaming tool output | 5 |
| 6 | **Context engine** | `ContextEngine` ABC: token budgeting, protected system-prompt + recent window, LLM summarization of older turns; retrieval upgraded from SQL `LIKE` to FTS5 with recency scoring. | ContextEngine ABC, micro-compaction, FTS5 search | 8 |
| 7 | **Interrupts, approvals & safety** | Executor-level interrupt before `ToolNode` when a tool needs approval (CLI confirm → resume from checkpoint, needs #4); per-tool timeouts; graceful Ctrl-C → checkpoint. | approvals.mode, interrupt_control, fail-closed design | — |
| 8 | **Sandboxed code-execution tool** | A `run_python`/shell tool for data wrangling in finance research, with timeouts, gated by #7's approval mechanism; local subprocess first, container isolation later. | Terminal backends, code_execution_tool, approval.py | 6 |
| 9 | **Subagent node & multi-agent runtime + measurement** | `SubAgentNode`: nested `GraphExecutor` with fresh state/session, own run-id namespace linked via `parent_event_id`, structured result into a parent channel; optional parallel fan-out (needs #5); trajectory-level eval scoring to compare loop vs graph vs subagent runs. | `delegate_task`: fresh context, structured outputs, budgets | 5 |
| 10 | **Skills 2.0: progressive disclosure** | Catalog stays tiny in the system prompt; full skill body loads on demand via a `load_skill` tool (replacing the first-line `{"skill": ...}` protocol); optional `save_skill` so the agent writes its own procedures. | Skills, progressive disclosure, self-authored skills | 7 |

**Waves:** Wave A: #1, #2, #3 → Wave B: #4, #5, #6, #7 → Wave C: #8, #9, #10.

**Explicitly later/optional:** sandboxed container backends, messaging-gateway adapters,
self-improving skill loops, OAuth provider flows, embeddings-based semantic memory.

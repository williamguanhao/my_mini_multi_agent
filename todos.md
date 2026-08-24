# Todo — Graph Agent Work (complete)

## Status snapshot

Graph agent is wired and verified. `mini_agent/graph_agent.GraphAgent` is a drop-in alternative to `mini_agent.agent.Agent` with the same external shape (`run(user_input) -> AgentResult`). It exists side by side with the loop-based agent; no changes to `Agent` / `AgentLoop` / `run_eval.py` / `main.py`.

7 graph tests pass. 1 pre-existing unrelated test (`test_conditional_graph_routing.py`) still fails to collect due to a relative-import issue from before this session — out of scope.

## What's done

- [x] `tests/test_graph_agent.py` — 2 tests with FakeLLM / FakeToolExecutor / FakeMessageStore etc — PASS
- [x] `mini_agent/graph_agent.py` — `ThinkNode`, `ActNode`, `AnswerNode`, `_build_graph`, `GraphAgent` — PASS
- [x] `graph/executor.py` — completed refactor:
  - Added `_node_failed(run_id, node, state, error)` helper
  - Calls `event_factory.edge_traversed(..., route=edge.name, ...)` and `event_factory.node_failed(run_id, node_name=node.name, state=state, error=error)`
- [x] `graph/edge.py` — fixed `Edge.route: str | None = None,` (stray trailing comma → invalid tuple annotation)
- [x] `graph/graph.py` — made `route` optional in `Graph.add_edge(...)` so call sites without route still work
- [x] `mini_agent/event_factory.py` — signature alignments:
  - `edge_traversed` now accepts `route: str | None = None`
  - `node_failed` now takes `(run_id, node_name, state, error)` and emits `event_type="node_failed"`
- [x] `mini_agent/graph_agent.py` — `if self.event_factory is not None:` guards at each event call site in `ThinkNode.execute` and `ActNode.execute` (mirrors `GraphExecutor._node_started` pattern)

## What's still broken (out of scope, pre-existing)

- `tests/test_conditional_graph_routing.py` — uses `from ..graph.node import ...` which fails because `tests/` is not a package. Pre-dates this session. Needs `tests/__init__.py` or absolute imports.

## Verification

```bash
python -m pytest tests/ --ignore=tests/test_conditional_graph_routing.py -v
# 7 passed in 0.02s
```

| Test | Result |
|---|---|
| `test_graph_agent.py::test_graph_agent_simple_qa_no_tool` | PASS |
| `test_graph_agent.py::test_graph_agent_tool_call_then_answer` | PASS |
| `test_graph_executor.py::test_edge_to_end_terminates_without_lookup_error` | PASS |
| `test_graph_executor.py::test_two_node_chain_ending_at_end_terminates` | PASS |
| `test_react_graph.py::test_react_loops_until_llm_says_done` | PASS |
| `test_react_graph.py::test_react_terminates_immediately_when_no_tool_needed` | PASS |
| `test_react_graph.py::test_react_calls_each_tool_with_decision_args` | PASS |

## Files touched this session

| File | Change |
|---|---|
| `graph/edge.py` | fixed `route: str \| None = None,` annotation |
| `graph/graph.py` | made `add_edge`'s `route` parameter optional |
| `graph/executor.py` | added `_node_failed` helper |
| `mini_agent/event_factory.py` | `edge_traversed` gained `route=` param; `node_failed` aligned to `(run_id, node_name, state, error)` with event_type `node_failed` |
| `mini_agent/graph_agent.py` | `event_factory is not None` guards in `ThinkNode` and `ActNode` |
| `todos.md` | this update
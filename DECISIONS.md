# Architecture Decisions

## Why doing this?
Following waku agent. This project is a step by step agent builder that helps understand each layer of agent harness. Later will explore loop and graphic ai agent design.
https://github.com/ShenSeanChen/waku-agent/tree/main/waku

## LLM Providers

We use MiniMax through its OpenAI-compatible API.

Reason:
- Familiar OpenAI SDK interface
- Still in the discription
- Keeps the LLM layer provider-independent
- Allows us to focus on agent architecture
---

## Agent Loop

The agent loop is responsible for:

1. Send messages to LLM
2. Inspect response
3. Detect tool calls
4. Execute tools
5. Append tool results
6. Call LLM again
7. Return final answer

---

## Tool Architecture

Tools are represented by a Tool object containing:

- name
- description
- parameters
- function

ToolRegistry maps tool names to Tool objects.

---

## Learning Strategy

We intentionally implement the mechanism manually before
introducing abstractions.

This allows us to understand what the framework abstractions
are hiding.

## Agent as Node (2026-09-13)

Decision: canonical agent nodes live in `mini_agent/nodes/`, NOT in `graph/`.

Reason:
- `graph/` is the execution engine and must stay LLM-agnostic
  (narrow waist). `AgentNode` needs `ModelClient`, `ContextProvider`,
  and tool schemas — those are capability-layer concerns.
- Same split as langgraph: `langgraph.graph` (engine) vs
  `langgraph.prebuilt` (ready-made model-aware nodes).
- Precedent set for later nodes (GuardNode/approvals #7,
  SubAgentNode #9): capability at the edges, engine untouched.

Related decisions:
- `run_id` and other run-scoped values flow through `GraphState`,
  not node constructors → nodes are stateless across runs and the
  graph is built once.
- Run lifecycle events (`run_started/completed/failed`) are owned by
  the agent (GraphAgent / AgentLoop), not by nodes or the executor.
- `GraphExecutor` owns `state.step`; nodes must not increment it.
- Tool-call shape normalization lives in exactly one place:
  `mini_agent/tool_calls.py`.

Learning notebook: `notebooks/01_agent_as_node.ipynb`.

## Finance research

## Finance derivative pricing
# Learning Changelog

Phase 1  ██████████   Refactor the existing Agent Loop
Phase 2  ██████████   Make tracing first-class
Phase 3  ██████████   Build the Graph Engine
Phase 4  ██████████   Agent as Graph Node
Phase 5  ░░░░░░░░░░   Multi-Agent Runtime
Phase 6  ░░░░░░░░░░   Real Research Tools
Phase 7  ░░░░░░░░░░   Skills
Phase 8  ░░░░░░░░░░   Upgrade Memory + Eval
Phase 9  ░░░░░░░░░░   Integrate derivative pricing models
Phase 10 ░░░░░░░░░░   Build financial research & pricing agent

## Foundation hardening — 2026-09-13 (before Phase 4)

Full plan: [docs/ROADMAP.md](docs/ROADMAP.md). Learning notes: [LEARNING_PATH.md](LEARNING_PATH.md).

### Added
- `.env.example`; `.env` untracked from git (working copy kept)
- root `conftest.py` so tests import `mini_agent` / `graph` / `mcp_servers.*` reliably
- dev dependency group (pytest, pytest-cov, ruff, mypy) + uv workspace over the 3 MCP servers
- GitHub Actions CI (ruff + pytest, empty credentials by design)
- eval harness rebuilt on the current `Event`/`EventBus` API; `agent-eval` works again;
  `tests/test_eval.py` covers scoring with fakes
- shared system prompt `mini_agent/prompts.py` (was duplicated in 3 places)

### Fixed
- `agent_loop._fail`: `state.error = error,` stored a tuple, not the exception
- `GraphExecutor.run`: loop iterated `max_steps` (crash on `None`) instead of `step_limit`
- `EventFactory.node_started`: embedded a live `GraphState` object (not JSON-serializable);
  now stores `state.snapshot()`
- `test_conditional_graph_routing.py` never collected (relative import in non-package);
  rewritten with absolute imports and real assertions

### Changed
- removed dead code: `graph/runner.py` (typo `exexutor`), `graph/agent_graph.py`,
  old `graph/nodes/*` (called nonexistent `agent.complete()`), demo node stubs in
  `graph/node.py`, stale `eval/runEval.py`, `mini_agent/trace/replay.py`,
  `agent_decision.py`, `trace_handler.py`, `mini_agent/test_replay.py`
- `print` → `logging` in agent, event bus, trace collector, context, main, runtime
- `mcp[cli]<2` pinned in `mcp_servers/yfinance` (matches root + D1 lesson)

## Phase 3 — Build the Graph Engine

### Added
- Graph Engine
- Routing

                         GRAPH
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
          NODE A        NODE B        NODE C
             │             │             │
             └─────────────┼─────────────┘
                           │
                         EDGES
                           │
              determines movement
                           │
                           ▼
                     GRAPH STATE
                           │
               stores execution data
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          question      research      analysis

                 ┌───────────────────┐
                 │   Current State   │
                 └─────────┬─────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    NODE     │
                    │             │
                    │ execute()   │
                    └──────┬──────┘
                           │
                     updates state
                           │
                           ▼
                 ┌───────────────────┐
                 │   Updated State   │
                 └─────────┬─────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │    EDGE     │
                    │             │
                    │ route based │
                    │ on state     │
                    └──────┬──────┘
                           │
                           ▼
                    Next Node
                           │
                           └───────────┐
                                       │
                                       ▼
                               Current State

AgentNode
 └── does one unit of work

Router
 └── decides what happens next

Edge
 └── connects things

GraphExecutor
 └── controls execution

GraphState
 └── carries information

EventBus / RunTrace
 └── observes execution

Changing from 

Agent
 │
 └── AgentLoop
      │
      ├── think
      ├── act
      ├── observe
      └── repeat

to Now

GraphExecutor
 │
 └── AgentGraph
      │
      ├── AgentNode
      ├── Router
      ├── ToolNode
      └── Edge → AgentNode

### Learned

### Structural change

## Phase 2 — Make tracing first-class

### Added
- trace each event that loop emits
- conver trace into event handler
- make traces queryable and replayable instead of just logs
- trace store in memory
- replay trace

                         Agent
                           │
                           ▼
                      AgentLoop
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
 ContextProvider      ModelClient        Runtime
          │                │                │
          │                │                ▼
          │                │             Registry
          │                │
          └────────────────┘
                   │
                   ▼
             MessageStore


AgentLoop
    │
    │ publishes events
    ▼
 EventBus
    │
    ├───────────────┬─────────────────┐
    ▼               ▼                 ▼
ConsoleTracer   JsonTracer      TraceCollector
                                      │
                                      ▼
                                  RunTrace
                                      │
                                      ▼
                              SQLiteTraceStore

- Structured trace
    {
      "event_id": "2d4f79a6-6b87-4e70-b414-68052ca24e19",
      "event_type": "tool_started",
      "run_id": "af1f643c-6b40-4a89-9908-e75c49d3bda2",
      "timestamp": 1787406058.856359,
      "sequence": 4,
      "step": 1,
      "parent_event_id": null,
      "payload": {
        "tool": "calculator"
      }
    },

    {
      "event_id": "7036ef54-a4f4-4124-ac20-78c0b85c893b",
      "event_type": "tool_completed",
      "run_id": "af1f643c-6b40-4a89-9908-e75c49d3bda2",
      "timestamp": 1787406058.856606,
      "sequence": 5,
      "step": 1,
      "parent_event_id": "2d4f79a6-6b87-4e70-b414-68052ca24e19",
      "payload": {
        "tool": "calculator",
        "success": true
    },

- trace stored
runs
│
├── run_id
├── input
├── started_at
├── ended_at
├── status
├── output
└── metadata

events
│
├── event_id
├── run_id
├── event_type
├── timestamp
├── sequence
├── step
├── parent_event_id
└── payload

### Learned

### Structural change
mini_agent/
      ├── __init__.py
      ├── config.py
      ├── tool.py
      ├── registry.py
      ├── session.py
      ├── memory.py
      ├── retrieval.py
      ├── gateway.py
      ├── runtime.py
      ├── tracer.py
      ├── main.py                     # modified
      ├── agent.py                   # modified
      │
      ├── [NEW] agent_loop.py        # modified
      ├── [NEW] agent_state.py
      ├── [NEW] agent_result.py
      ├── [NEW] context.py
      ├── [NEW] model.py
      ├── [NEW] message_store.py
      ├── [NEW] tool_executor.py
      ├── [NEW] tool_result.py
      │
      ├── [NEW] event_bus.py
      ├── [NEW] event_factory.py
      ├── [NEW] event_handler.py
      ├── [NEW] events.py
      ├── [NEW] trace_handler.py
      ├── [NEW] console_tracer.py
      ├── [NEW] json_tracer.py
      │
      ├── tools/
      │   ├── __init__.py
      │   ├── time.py
      │   ├── calculator.py
      │   ├── save_note.py
      │   └── read_notes.py
      │
      ├── llm/
      │   ├── __init__.py
      │   ├── base.py
      │   ├── minimax.py
      │   ├── openai.py
      │   └── openrouter.py
      │
      └── eval/
          ├── __init__.py
          ├── case.py
          ├── cases.py
          ├── runEval.py
          └── runner.py

## Phase 1 — Refactor the existing Agent Loop

### Added
- refactore to agentloop
- adding agent state
- adding agent result 
- isolate agent execution boundaries

                         User
                          │
                          ▼
                        Agent
                          │
                          ▼
                     AgentLoop
                          │
            ┌─────────────┼──────────────┼───────────────┐
            │             │              │               │
            ▼             ▼              ▼               ▼ 
        Retriever      Gateway        Runtime         AgentState
            │             │              │               │
            ▼             ▼              ▼               ▼
         Session          LLM         Registry        AgentResult
            │                            │
            ▼                            ▼
          Memory                        Tool

### Learned
- Agent loop, status, result expanded for allow future change into node
- Agent Loop orchestrates. It should not know implementation details.

### Structural change

mini_agent/
├── agent.py.           <-New
├── agent_loop.py       <-New
├── agent_state.py      <-New
├── agent_result.py      <-New
├── config.py
├── gateway.py
├── memory.py
├── session.py
├── retriever.py
├── runtime.py
├── registry.py  
├── tool.py       
├── main.py
├── run_eval.py        
├── tracer.py          
├── llm/
    ├── __init__.py
    ├── base.py
    ├── minimax.py
    ├── openai.py
    └── openrouter.py
├── eval/               
    ├── __init__.py     
    ├── case.py         
    ├── cases.py        
    └── runner.py       
└──  tools/           
    ├── __init__.py
    ├── time.py
    ├── calculator.py
    ├── save_note.py
    └── read_note.py

## Phase 2 — Make tracing first-class



## Phase 3 — Build the Graph Engine



## Phase 4 — Agent as Graph Node

### Added
- canonical nodes in `mini_agent/nodes/`: `AgentNode` (context → model → decision),
  `ToolNode` (executes decision calls, appends `tool_calls_log`, persists results,
  links `tool_completed` → `tool_started`), `AnswerNode`, `DecisionRouter`,
  and `state_keys.py` (the five-key state contract)
- `mini_agent/tool_calls.py`: single tool-call shape normalizer
  (`tool_call_name` / `tool_call_arguments` / `parse_tool_arguments`),
  replacing three drifted copies in `AgentLoop`, `Runtime`, and the old `ActNode`
- `tests/test_agent_nodes.py`: 12 node-level tests (decisions, event linkage,
  no-tracing paths, router, run reuse and isolation)
- learning notebook `notebooks/01_agent_as_node.ipynb` (executed, fake-based)

### Changed
- `GraphAgent` rewritten as a thin builder: graph built **once** in `__init__`
  (was rebuilt every run with `run_id` baked into node constructors);
  `run_id`/`user_input` flow through `GraphState`
- `GraphAgent` now publishes `run_started`/`run_completed`/`run_failed`
  (mirrors `AgentLoop`; graph runs persist in `SQLiteTraceStore` from now on)
- `GraphExecutor` is the single owner of `state.step` (was double-incremented
  by the old `ThinkNode`); `max_steps` mapping documented: `2 * max_steps + 2`
- `Runtime._get_tool_name` raises via the shared normalizer (error path uses
  `default="<unknown>"` to stay safe inside `except`)

### Learned
- nodes must be stateless across runs: infrastructure identity belongs in state
- capability nodes sit at the edge (`mini_agent/nodes/`), engine stays pure
  (`graph/`) — see DECISIONS.md "Agent as Node"

## Phase 5 — Multi-Agent Runtime



## Phase 6 — Real Research Tools



## Phase 7 — Skills



## Phase 8 — Upgrade Memory + Eval



## Phase 9 — Integrate derivative pricing models



## Phase 9 — Build financial research & pricing agent



## Target

                         ┌───────────────┐
                         │    Gateway    │
                         └───────┬───────┘
                                 │
                                 ▼
                      ┌────────────────────┐
                      │    Agent Runtime   │
                      │                    │
                      │  Run / State /     │
                      │  Context / Trace   │
                      └─────────┬──────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                │
               ▼                ▼                ▼
          Single Agent      Graph Agent      Multi-Agent
               │                │                │
               ▼                ▼                ▼
             Loop           Graph Engine     Agent Pool
               │                │                │
               └────────────────┼────────────────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
                 ▼              ▼              ▼
               Tools         Memory         Skills
                 │              │              │
                 └──────────────┼──────────────┘
                                ▼
                              Trace
                                │
                                ▼
                              Eval

## Original

### Flow
                    User
                      │
                      ▼
                 Agent.run()
                      │
             ┌────────┴─────────┐
             │                  │
          Session            Retriever
             │                  │
             └────────┬─────────┘
                      ▼
                  Gateway
                      │
                      ▼
                     LLM
                      │
              ┌───────┴────────┐
              │                │
          final answer       tool call
                                 │
                                 ▼
                              Runtime
                                 │
                                 ▼
                              Registry
                                 │
                                 ▼
                               Tool
                                 │
                                 ▼
                          Tool result
                                 │
                                 └──────► LLM

### Original architecture

mini_agent/
├── agent.py
├── config.py
├── gateway.py
├── memory.py
├── session.py
├── retriever.py
├── runtime.py
├── registry.py        
├── main.py
├── run_eval.py        
├── tracer.py          
├── llm/
    ├── __init__.py
    ├── base.py
    ├── minimax.py
    ├── openai.py
    └── openrouter.py
├── eval/               
    ├── __init__.py     
    ├── case.py         
    ├── cases.py        
    └── runner.py       
└──  tools/           
    ├── __init__.py
    ├── time.py
    ├── calculator.py
    ├── save_note.py
    └── read_note.py


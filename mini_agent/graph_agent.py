"""Graph-based agent — same external shape as mini_agent/agent.py,
but the control flow is a graph (think → act → think / answer → END)
instead of a hand-written for-loop.

This module is now a thin builder over the canonical nodes in
mini_agent/nodes/ (improvement #1: "agent as node"). The graph is
built once in __init__ and reused across runs: run-scoped values
(run_id, user_input) flow through GraphState, so nodes never bake
run identity into their constructors.

Graph topology:

    __start__ ──► think ─[tool]──► act ──► think   (loop while LLM keeps calling tools)
                    │
                    └─[answer]─► answer ──► __end__

Each node publishes the same events the loop agent would
(step_started, model_called, model_completed, tool_started, tool_completed)
so trace contents look the same regardless of which agent ran. The run
lifecycle events (run_started / run_completed / run_failed) are owned by
GraphAgent itself, mirroring AgentLoop.
"""

import uuid

from graph.executor import GraphExecutor
from graph.graph import Graph
from graph.state import GraphState

from .agent_result import AgentResult
from .nodes import (
    FINAL_OUTPUT,
    RUN_ID,
    TOOL_CALLS_LOG,
    USER_INPUT,
    AgentNode,
    AnswerNode,
    DecisionRouter,
    ToolNode,
)


class GraphAgent:
    """Same external shape as Agent, but implemented as a graph run."""

    def __init__(
            self,
            model_client,
            tool_executor,
            registry,
            context_provider,
            message_store,
            event_bus=None,
            event_factory=None,
    ):
        self.model_client = model_client
        self.tool_executor = tool_executor
        self.registry = registry
        self.context_provider = context_provider
        self.message_store = message_store
        self.event_bus = event_bus
        self.event_factory = event_factory

        # Built once; nodes are stateless across runs because run-scoped
        # values live in GraphState, not in the node instances.
        self._graph = self._build_graph()
        self._executor = GraphExecutor(
            event_bus=self.event_bus,
            event_factory=self.event_factory,
        )

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    def _build_graph(self) -> Graph:
        g = Graph()
        g.add_node("think", AgentNode(
            "think",
            model_client=self.model_client,
            context_provider=self.context_provider,
            registry=self.registry,
            message_store=self.message_store,
            event_bus=self.event_bus,
            event_factory=self.event_factory,
        ))
        g.add_node("act", ToolNode(
            "act",
            tool_executor=self.tool_executor,
            message_store=self.message_store,
            event_bus=self.event_bus,
            event_factory=self.event_factory,
        ))
        g.add_node("answer", AnswerNode("answer"))

        # Entry: __start__ → think
        g.add_edge(g.START, "think", route="entry")

        # After think: route by decision type
        g.add_conditional_edges(
            "think",
            DecisionRouter(),
            {"tool": "act", "answer": "answer"},
        )

        # After act: loop back to think (so LLM sees the tool results)
        g.add_edge("act", "think", route="loop")

        # After answer: terminate
        g.add_edge("answer", g.END, route="finish")

        return g

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, user_input: str, max_steps: int = 10) -> AgentResult:
        run_id = str(uuid.uuid4())

        self.message_store.add_user(user_input)

        if self.event_bus is not None and self.event_factory is not None:
            self.event_bus.publish(
                self.event_factory.run_start(run_id, user_input)
            )

        state = GraphState()
        state.set(USER_INPUT, user_input)
        state.set(RUN_ID, run_id)

        # Each tool round is think + act (2 nodes); the run ends with a
        # final think + answer (2 more). max_steps bounds tool rounds,
        # so the executor gets max_steps * 2 + 2 graph steps.
        graph_steps = max_steps * 2 + 2

        try:
            final = self._executor.run(
                self._graph,
                state,
                run_id=run_id,
                max_steps=graph_steps,
            )

            output = final.get(FINAL_OUTPUT)

            if self.event_bus is not None and self.event_factory is not None:
                self.event_bus.publish(
                    self.event_factory.run_completed(run_id, output)
                )

            return AgentResult(
                output=output,
                status="completed" if final.finished else "max_steps",
                iterations=final.step,
                tool_calls=final.get(TOOL_CALLS_LOG) or [],
                state=final,
            )
        except Exception as e:
            if self.event_bus is not None and self.event_factory is not None:
                self.event_bus.publish(
                    self.event_factory.run_failed(run_id, e)
                )
            return AgentResult(
                status="error",
                iterations=state.step,
                tool_calls=state.get(TOOL_CALLS_LOG) or [],
                state=state,
                error=e,
            )

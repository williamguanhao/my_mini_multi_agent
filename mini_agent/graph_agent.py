"""Graph-based agent — same external shape as mini_agent/agent.py,
but the control flow is a graph (think → act → think / answer → END)
instead of a hand-written for-loop.

Graph topology:

    __start__ ──► think ─[tool]──► act ──► think   (loop while LLM keeps calling tools)
                    │
                    └─[answer]─► answer ──► __end__

Each node publishes the same events the loop agent would
(step_started, model_called, model_completed, tool_started, tool_completed)
so trace contents look the same regardless of which agent ran.
"""

import uuid

from graph.node import Node
from graph.graph import Graph
from graph.router import FunctionRouter
from graph.state import GraphState
from graph.executor import GraphExecutor

from .agent_result import AgentResult


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class ThinkNode(Node):
    """Calls the model. Writes decision into state.values.

    decision = {"type": "tool",    "calls": [...tool_calls]}
             or {"type": "answer", "content": "..."}
    """

    def __init__(
            self,
            model_client,
            registry,
            context_provider,
            message_store,
            event_bus,
            event_factory,
            run_id,
    ):
        super().__init__("think")
        self.model_client = model_client
        self.registry = registry
        self.context_provider = context_provider
        self.message_store = message_store
        self.event_bus = event_bus
        self.event_factory = event_factory
        self.run_id = run_id

    def execute(self, state):
        # Step bookkeeping: think starts a new "step"
        step = state.step + 1
        state.step = step

        if self.event_factory is not None:
            self._publish(
                self.event_factory.step_started(self.run_id, step)
            )

        # Build context
        user_input = state.values.get("user_input", "")
        context = self.context_provider.build(user_input)
        messages = context.messages

        # Call model
        if self.event_factory is not None:
            self._publish(
                self.event_factory.model_called(self.run_id, step)
            )
        response = self.model_client.generate(
            messages=messages,
            tools=self.registry.schemas(),
        )
        if self.event_factory is not None:
            self._publish(
                self.event_factory.model_completed(
                    self.run_id,
                    len(response.tool_calls),
                    step,
                )
            )

        # Save assistant response
        self.message_store.add_assistant(response)

        # Decide
        if response.tool_calls:
            state.set(
                "decision",
                {"type": "tool", "calls": response.tool_calls},
            )
        else:
            state.set(
                "decision",
                {"type": "answer", "content": response.content},
            )

        return state

    def _publish(self, event):
        if self.event_bus is not None and event is not None:
            self.event_bus.publish(event)


class ActNode(Node):
    """Runs the tool calls in the current decision."""

    def __init__(
            self,
            tool_executor,
            message_store,
            event_bus,
            event_factory,
            run_id,
    ):
        super().__init__("act")
        self.tool_executor = tool_executor
        self.message_store = message_store
        self.event_bus = event_bus
        self.event_factory = event_factory
        self.run_id = run_id

    def execute(self, state):
        decision = state.get("decision") or {}
        if decision.get("type") != "tool":
            return state

        calls = decision.get("calls") or []
        results = []

        for tool_call in calls:
            tool_name = self._tool_name(tool_call)
            if self.event_factory is not None:
                tool_started = self.event_factory.tool_started(
                    self.run_id, tool_name, state.step,
                )
                self._publish(tool_started)

            result = self.tool_executor.execute(tool_call)
            results.append(result)

            if self.event_factory is not None:
                self._publish(
                    self.event_factory.tool_completed(
                        self.run_id,
                        result.name,
                        result.success,
                        state.step,
                        parent_event_id=tool_started.event_id,
                    )
                )

            self.message_store.add_tool(
                tool_call_id=result.tool_call_id,
                tool_name=result.name,
                content=result.content,
            )

        # Accumulate tool_calls_log for AgentResult
        log = list(state.get("tool_calls_log") or [])
        for r in results:
            log.append({
                "tool_call_id": r.tool_call_id,
                "name": r.name,
                "arguments": r.arguments,
                "content": r.content,
                "success": r.success,
            })
        state.set("tool_calls_log", log)

        return state

    def _publish(self, event):
        if self.event_bus is not None and event is not None:
            self.event_bus.publish(event)

    @staticmethod
    def _tool_name(tool_call) -> str:
        """Tool calls arrive in two shapes:

        - OpenAI-style:   tool_call.function.name
        - Custom style:   tool_call.name

        Mirror AgentLoop._tool_name so GraphAgent accepts both.
        """
        function = getattr(tool_call, "function", None)
        if function is not None:
            name = getattr(function, "name", None)
            if name:
                return name

        name = getattr(tool_call, "name", None)
        if name:
            return name

        raise ValueError(
            "Tool call does not contain a tool name."
        )


class AnswerNode(Node):
    """Writes the final assistant content into state as final_output."""

    def __init__(self):
        super().__init__("answer")

    def execute(self, state):
        decision = state.get("decision") or {}
        content = decision.get("content", "")
        state.set("final_output", content)
        return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_graph(
        model_client,
        tool_executor,
        registry,
        context_provider,
        message_store,
        event_bus,
        event_factory,
        run_id,
):
    g = Graph()
    g.add_node("think", ThinkNode(
        model_client=model_client,
        registry=registry,
        context_provider=context_provider,
        message_store=message_store,
        event_bus=event_bus,
        event_factory=event_factory,
        run_id=run_id,
    ))
    g.add_node("act", ActNode(
        tool_executor=tool_executor,
        message_store=message_store,
        event_bus=event_bus,
        event_factory=event_factory,
        run_id=run_id,
    ))
    g.add_node("answer", AnswerNode())

    # Entry: __start__ → think
    g.add_edge(g.START, "think", route="entry")

    # After think: route by decision type
    g.add_conditional_edges(
        "think",
        FunctionRouter(
            lambda s: "tool" if (s.get("decision") or {}).get("type") == "tool"
            else "answer"
        ),
        {"tool": "act", "answer": "answer"},
    )

    # After act: loop back to think (so LLM sees the tool results)
    g.add_edge("act", "think", route="loop")

    # After answer: terminate
    g.add_edge("answer", g.END, route="finish")

    return g


# ---------------------------------------------------------------------------
# Public agent
# ---------------------------------------------------------------------------

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

    def run(self, user_input: str, max_steps: int = 10) -> AgentResult:
        run_id = str(uuid.uuid4())

        self.message_store.add_user(user_input)

        state = GraphState()
        state.set("user_input", user_input)

        graph = _build_graph(
            model_client=self.model_client,
            tool_executor=self.tool_executor,
            registry=self.registry,
            context_provider=self.context_provider,
            message_store=self.message_store,
            event_bus=self.event_bus,
            event_factory=self.event_factory,
            run_id=run_id,
        )

        executor = GraphExecutor(
            event_bus=self.event_bus,
            event_factory=self.event_factory,
        )

        # Each "step" in the loop is 2-3 graph nodes; give the executor room.
        try:
            final = executor.run(
                graph, state, run_id=run_id, max_steps=max_steps * 4,
            )
            return AgentResult(
                output=final.get("final_output"),
                status="completed" if final.finished else "max_steps",
                iterations=final.step,
                tool_calls=final.get("tool_calls_log") or [],
                state=final,
            )
        except Exception as e:
            return AgentResult(
                status="error",
                iterations=state.step,
                tool_calls=state.get("tool_calls_log") or [],
                state=state,
                error=e,
            )

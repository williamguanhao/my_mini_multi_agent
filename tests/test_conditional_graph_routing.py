"""Conditional-routing tests for the graph engine.

Covers the two routing mechanisms:
  - router-based conditional edges (add_conditional_edges + AgentRouter)
  - predicate edges (Edge.condition)

Uses throwaway fake nodes so the test does not depend on any
concrete agent implementation.
"""

from graph.executor import GraphExecutor
from graph.graph import Graph
from graph.node import Node
from graph.router import AgentRouter
from graph.state import GraphState


class FakeAgentNode(Node):
    """Decides what to do next: call a tool, or finish."""

    def execute(self, state: GraphState) -> GraphState:
        if state.get("tool_result"):
            state.set("done", True)
        else:
            state.set("tool_required", True)
        return state


class FakeToolNode(Node):
    """Pretends to run a tool and feeds the result back."""

    def execute(self, state: GraphState) -> GraphState:
        state.set("tool_result", "search result")
        state.set("tool_required", False)
        return state


def _build_graph() -> Graph:
    graph = Graph()
    graph.add_node("agent", FakeAgentNode("agent"))
    graph.add_node("tool", FakeToolNode("tool"))
    graph.add_edge(Graph.START, "agent", "start_run")
    graph.add_conditional_edges(
        "agent",
        AgentRouter(),
        {
            "tool": "tool",
            "end": Graph.END,
        },
    )
    graph.add_edge("tool", "agent", "back_to_agent")
    return graph


def test_conditional_routing_loops_tool_then_ends():
    graph = _build_graph()

    final_state = GraphExecutor().run(graph, GraphState(), run_id="route-test")

    assert final_state.finished is True
    assert final_state.get("tool_result") == "search result"
    assert final_state.get("done") is True


def test_predicate_edge_routes_on_condition():
    graph = Graph()
    graph.add_node("a", FakeAgentNode("a"))
    graph.add_node("tool", FakeToolNode("tool"))
    graph.add_edge(Graph.START, "a")
    # Predicate edge: only taken when a tool result already exists.
    graph.add_edge("a", Graph.END, name="finish", condition=lambda s: s.get("done"))
    graph.add_edge("a", "tool", name="use_tool", condition=lambda s: not s.get("done"))
    graph.add_edge("tool", "a", name="back")

    final_state = GraphExecutor().run(graph, GraphState(), run_id="predicate-test")

    assert final_state.finished is True
    assert final_state.get("tool_result") == "search result"


def test_agent_router_choices():
    router = AgentRouter()

    done_state = GraphState()
    done_state.set("done", True)
    assert router.route(done_state) == "end"

    tool_state = GraphState()
    tool_state.set("tool_required", True)
    assert router.route(tool_state) == "tool"

    assert router.route(GraphState()) == "end"

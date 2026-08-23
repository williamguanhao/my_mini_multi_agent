"""ReAct agent expressed as a graph with conditional edges.

Graph shape:
    __start__ ──► think ──► act ──► observe ──► __end__
                   ▲                    │
                   └──── loop ──────────┘  (until finished)

- think:    asks the LLM, parses decision (tool call or answer),
            sets state.values["finished"] when decision is an answer.
- act:      if decision is a tool call, invokes the tool, records result.
- observe:  appends the tool result to history.

Conditional edges:
- think    → act        if decision.type == "tool"
- think    → __end__    otherwise
- observe  → think      if not state.values["finished"]
- observe  → __end__    otherwise

LLM and tools are fakes (no API calls, deterministic). All graph
infrastructure is loaded via importlib because graph/__init__.py is empty.
"""

import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "graph"


# ---------------------------------------------------------------------------
# importlib loader (kept local; user asked for no changes to other files).
# Registers graph_pkg as a real package so `from .state import ...` works.
# ---------------------------------------------------------------------------

def _ensure_package():
    if "graph_pkg" not in sys.modules:
        pkg = types.ModuleType("graph_pkg")
        pkg.__path__ = [str(GRAPH_DIR)]
        sys.modules["graph_pkg"] = pkg


def _load(mod_name, file_name):
    _ensure_package()
    full_name = f"graph_pkg.{mod_name}"
    spec = importlib.util.spec_from_file_location(
        full_name, str(GRAPH_DIR / file_name)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    setattr(sys.modules["graph_pkg"], mod_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def graph_pkg():
    state = _load("state", "state.py")
    edge = _load("edge", "edge.py")
    node = _load("node", "node.py")
    graph_mod = _load("graph", "graph.py")
    # executor.py uses `from .graph import Graph` and `from .state import GraphState`
    sys.modules["graph"] = graph_mod
    sys.modules["state"] = state
    _load("executor", "executor.py")
    return {
        "Graph": graph_mod.Graph,
        "GraphState": state.GraphState,
        "Node": node.Node,
    }


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeToolCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class FakeLLMResponse:
    """Mirrors what the real LLMResponse carries: optional tool call,
    optional content. Both can be set; the ThinkNode reads whichever is
    populated."""

    def __init__(self, content=None, tool_call=None):
        self.content = content
        self.tool_call = tool_call


class FakeLLM:
    """Scripted LLM. Pops the next response on each complete() call.
    Records every call so tests can assert what was asked."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def complete(self, messages):
        self.calls.append(list(messages))
        if not self._scripted:
            raise RuntimeError("FakeLLM ran out of scripted responses")
        return self._scripted.pop(0)


class FakeTool:
    """Records every invocation and returns a preset result."""

    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.invocations = []

    def invoke(self, args):
        self.invocations.append(args)
        return self._result


# ---------------------------------------------------------------------------
# ReAct nodes
# ---------------------------------------------------------------------------

def _make_think_node(NodeCls):
    class ThinkNode(NodeCls):
        def __init__(self, llm, name="think"):
            super().__init__(name)
            self.llm = llm

        def execute(self, state):
            messages = list(state.get("messages", []))
            response = self.llm.complete(messages)
            if response.tool_call is not None:
                decision = {
                    "type": "tool",
                    "name": response.tool_call.name,
                    "args": response.tool_call.args,
                }
                state.set("decision", decision)
                state.set("finished", False)
            else:
                decision = {"type": "answer", "content": response.content}
                state.set("decision", decision)
                state.set("finished", True)
            state.set(
                "messages",
                messages + [
                    {
                        "role": "assistant",
                        "content": response.content,
                        "tool_call": (
                            None
                            if response.tool_call is None
                            else {
                                "name": response.tool_call.name,
                                "args": response.tool_call.args,
                            }
                        ),
                    }
                ],
            )
            return state
    return ThinkNode


def _make_act_node(NodeCls):
    class ActNode(NodeCls):
        def __init__(self, tools, name="act"):
            super().__init__(name)
            self.tools = tools  # dict[name -> tool-like]

        def execute(self, state):
            decision = state.get("decision")
            if not decision or decision["type"] != "tool":
                return state
            tool = self.tools[decision["name"]]
            result = tool.invoke(decision["args"])
            state.set("tool_result", result)
            return state
    return ActNode


def _make_observe_node(NodeCls):
    class ObserveNode(NodeCls):
        def __init__(self, name="observe"):
            super().__init__(name)

        def execute(self, state):
            history = list(state.get("history", []))
            history.append(state.get("tool_result"))
            state.set("history", history)
            return state
    return ObserveNode


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_react_graph(graph_pkg, llm, tools):
    """Build a ReAct graph with conditional edges:
    - think → act    if decision.type == "tool"
    - think → END    otherwise
    - observe → think if not finished
    - observe → END   if finished
    """
    Graph = graph_pkg["Graph"]
    Node = graph_pkg["Node"]
    ThinkNode = _make_think_node(Node)
    ActNode = _make_act_node(Node)
    ObserveNode = _make_observe_node(Node)

    g = Graph()
    g.add_node("think", ThinkNode(llm))
    g.add_node("act", ActNode(tools))
    g.add_node("observe", ObserveNode())
    g.add_edge(g.START, "think")
    g.add_edge(
        "think", "act",
        condition=lambda s: s.get("decision", {}).get("type") == "tool",
    )
    g.add_edge(
        "think", g.END,
        condition=lambda s: s.get("decision", {}).get("type") != "tool",
    )
    g.add_edge("act", "observe")
    g.add_edge(
        "observe", "think",
        condition=lambda s: not s.get("finished", False),
    )
    g.add_edge(
        "observe", g.END,
        condition=lambda s: s.get("finished", False),
    )
    return g


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_react_loops_until_llm_says_done(graph_pkg):
    """Two tool iterations, then LLM returns an answer → graph terminates."""
    calculator = FakeTool("calculator", "4")
    lookup = FakeTool("lookup", "Paris")
    llm = FakeLLM(
        scripted=[
            FakeLLMResponse(tool_call=FakeToolCall("calculator", {"expr": "2+2"})),
            FakeLLMResponse(tool_call=FakeToolCall("lookup", {"q": "capital of France"})),
            FakeLLMResponse(content="The answer is 4, the capital is Paris."),
        ]
    )

    g = _build_react_graph(graph_pkg, llm, {"calculator": calculator, "lookup": lookup})
    GraphExecutor = sys.modules["graph_pkg.executor"].GraphExecutor
    final = GraphExecutor().run(g, run_id="react-loop")

    assert final.finished is True
    assert final.current_node == g.END
    # think + act + observe, twice = 6 executions, plus one more think
    # that produces the final answer (7 total)
    assert final.step == 7
    # Both tools were called exactly once
    assert len(calculator.invocations) == 1
    assert calculator.invocations[0] == {"expr": "2+2"}
    assert len(lookup.invocations) == 1
    assert lookup.invocations[0] == {"q": "capital of France"}
    # History has both tool results, in order
    assert final.get("history") == ["4", "Paris"]
    # LLM was called 3 times (2 tool turns + final answer turn)
    assert len(llm.calls) == 3
    # Final decision is the answer, finished flagged
    assert final.get("decision") == {
        "type": "answer",
        "content": "The answer is 4, the capital is Paris.",
    }


def test_react_terminates_immediately_when_no_tool_needed(graph_pkg):
    """First LLM response is an answer → think → END with one node run."""
    llm = FakeLLM(scripted=[FakeLLMResponse(content="Just 42.")])
    calculator = FakeTool("calculator", "unused")

    g = _build_react_graph(graph_pkg, llm, {"calculator": calculator})
    GraphExecutor = sys.modules["graph_pkg.executor"].GraphExecutor
    final = GraphExecutor().run(g, run_id="react-immediate")

    assert final.finished is True
    assert final.current_node == g.END
    assert final.step == 1  # only think ran
    assert len(llm.calls) == 1
    assert calculator.invocations == []  # tool never called
    assert final.get("history", []) == []  # no observations recorded


def test_react_calls_each_tool_with_decision_args(graph_pkg):
    """Verify the exact args the ThinkNode parsed reach the tool."""
    seen_args = []
    captured_tool = FakeTool("echo", None)

    original_invoke = captured_tool.invoke

    def recording_invoke(args):
        seen_args.append(args)
        captured_tool._result = args  # return args as result so we can inspect
        return original_invoke(args)

    captured_tool.invoke = recording_invoke

    llm = FakeLLM(
        scripted=[
            FakeLLMResponse(
                tool_call=FakeToolCall("echo", {"hello": "world", "n": 3})
            ),
            FakeLLMResponse(content="done"),
        ]
    )

    g = _build_react_graph(graph_pkg, llm, {"echo": captured_tool})
    GraphExecutor = sys.modules["graph_pkg.executor"].GraphExecutor
    final = GraphExecutor().run(g, run_id="react-args")

    assert final.finished is True
    assert final.step == 4  # think, act, observe, think
    assert seen_args == [{"hello": "world", "n": 3}]
    # The tool's result was observed into history
    assert final.get("history") == [{"hello": "world", "n": 3}]

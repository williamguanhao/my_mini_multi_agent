"""End-to-end tests for mini_agent/graph_agent.py.

Exercises GraphAgent.run() against fake model + tool executor.
Proves the graph topology works:
  - simple Q&A: think → answer → __end__
  - tool path:   think → act → think → answer → __end__

Loads graph/ modules via importlib (graph/__init__.py is empty).
"""

import importlib.util
import pathlib
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "graph"


def _ensure_graph_pkg():
    if "graph_pkg" not in sys.modules:
        pkg = types.ModuleType("graph_pkg")
        pkg.__path__ = [str(GRAPH_DIR)]
        sys.modules["graph_pkg"] = pkg


def _load(mod_name, file_name):
    _ensure_graph_pkg()
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
    router = _load("router", "router.py")

    # Register a "graph" alias as a real package so that
    # `from graph.node import Node` (used in graph_agent.py) resolves.
    if "graph" not in sys.modules or not hasattr(sys.modules.get("graph"), "__path__"):
        graph_pkg_alias = types.ModuleType("graph")
        graph_pkg_alias.__path__ = [str(GRAPH_DIR)]
        sys.modules["graph"] = graph_pkg_alias
    sys.modules["graph"].node = node
    sys.modules["graph"].graph = graph_mod
    sys.modules["graph"].state = state
    sys.modules["graph"].router = router
    sys.modules["graph"].edge = edge
    sys.modules["graph"].Graph = graph_mod.Graph
    sys.modules["graph"].GraphState = state.GraphState
    sys.modules["graph"].Node = node.Node
    sys.modules["graph"].FunctionRouter = router.FunctionRouter

    # executor.py uses `from .graph import Graph` (relative) and
    # originally `from state import GraphState` — also alias "state".
    sys.modules["state"] = state

    _load("executor", "executor.py")
    return {
        "Graph": graph_mod.Graph,
        "GraphState": state.GraphState,
        "Node": node.Node,
        "FunctionRouter": router.FunctionRouter,
    }


# ---------------------------------------------------------------------------
# Fakes for the dependencies GraphAgent expects
# ---------------------------------------------------------------------------

class FakeMessageStore:
    def __init__(self):
        self.user_messages = []
        self.assistant_messages = []
        self.tool_messages = []

    def add_user(self, content):
        self.user_messages.append(content)

    def add_assistant(self, response):
        self.assistant_messages.append(response)

    def add_tool(self, tool_call_id, tool_name, content):
        self.tool_messages.append(
            {"call_id": tool_call_id, "name": tool_name, "content": content}
        )


class FakeContextProvider:
    def __init__(self):
        self.last_input = None

    def build(self, user_input):
        self.last_input = user_input
        # Mimic the shape the loop expects: object with .messages
        return types.SimpleNamespace(messages=[])


class FakeRegistry:
    def schemas(self):
        return []


class FakeFunction:
    """OpenAI-style tool_call.function wrapper."""

    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, name, arguments, call_id=None):
        self.function = FakeFunction(name, arguments)
        self.id = call_id or f"call_{name}_{id(self)}"


class FakeResponse:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeModelClient:
    """Scripted model. generate(messages=..., tools=...) pops the next response."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def generate(self, messages, tools):
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self._scripted:
            raise RuntimeError("FakeModelClient ran out of scripted responses")
        return self._scripted.pop(0)


class FakeToolExecutor:
    """Records each call, returns a preset ToolResult."""

    def __init__(self, results_by_name):
        self._results = results_by_name
        self.calls = []

    @staticmethod
    def _resolve(tool_call):
        """Accept both OpenAI-style (.function.name) and custom-style (.name)."""
        function = getattr(tool_call, "function", None)
        if function is not None:
            return (
                getattr(function, "name", None),
                getattr(function, "arguments", None),
            )
        return (
            getattr(tool_call, "name", None),
            getattr(tool_call, "arguments", None),
        )

    def execute(self, tool_call):
        self.calls.append(tool_call)
        from mini_agent.tool_result import ToolResult
        name, arguments = self._resolve(tool_call)
        result = self._results.get(name)
        if result is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=name,
                arguments=arguments,
                content=f"no result for {name}",
                success=False,
            )
        return ToolResult(
            tool_call_id=tool_call.id,
            name=name,
            arguments=arguments,
            content=result,
            success=True,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_graph_agent_simple_qa_no_tool(graph_pkg):
    """Single LLM call returns an answer → graph goes think → answer → END."""
    from mini_agent.graph_agent import GraphAgent

    model = FakeModelClient([FakeResponse(content="Hello to you too!")])
    message_store = FakeMessageStore()
    agent = GraphAgent(
        model_client=model,
        tool_executor=FakeToolExecutor({}),
        registry=FakeRegistry(),
        context_provider=FakeContextProvider(),
        message_store=message_store,
        event_bus=None,
        event_factory=None,
    )

    result = agent.run("Hi")

    assert result.output == "Hello to you too!"
    assert result.status == "completed"
    assert result.error is None
    assert len(model.calls) == 1
    assert message_store.user_messages == ["Hi"]
    assert len(message_store.assistant_messages) == 1
    assert message_store.tool_messages == []


class CustomStyleToolCall:
    """Real LLM in this project returns tool_calls with `.name` and `.arguments`
    directly on the object — not the OpenAI-style `.function.name` shape.
    Regression test: GraphAgent must accept both shapes.
    """

    def __init__(self, name, arguments, call_id=None):
        self.name = name
        self.arguments = arguments
        self.id = call_id or f"call_{name}_{id(self)}"


def test_graph_agent_custom_style_tool_call(graph_pkg):
    """Tool call where the object has `.name`/`.arguments` directly, no `.function`."""
    from mini_agent.graph_agent import GraphAgent

    tool_response = FakeResponse(
        tool_calls=[CustomStyleToolCall("calculator", {"expr": "456*454"})]
    )
    final_response = FakeResponse(content="206,464")
    model = FakeModelClient([tool_response, final_response])
    message_store = FakeMessageStore()
    tools = FakeToolExecutor({"calculator": "206464"})

    agent = GraphAgent(
        model_client=model,
        tool_executor=tools,
        registry=FakeRegistry(),
        context_provider=FakeContextProvider(),
        message_store=message_store,
        event_bus=None,
        event_factory=None,
    )

    result = agent.run("what is 456*454?")

    assert result.output == "206,464"
    assert result.status == "completed"
    assert len(tools.calls) == 1
    assert tools.calls[0].name == "calculator"


def test_graph_agent_tool_call_then_answer(graph_pkg):
    """LLM asks for a tool, gets the result, then returns a final answer."""
    from mini_agent.graph_agent import GraphAgent

    tool_response = FakeResponse(
        tool_calls=[FakeToolCall("calculator", {"expr": "2+2"})]
    )
    final_response = FakeResponse(content="The answer is 4.")
    model = FakeModelClient([tool_response, final_response])
    message_store = FakeMessageStore()
    tools = FakeToolExecutor({"calculator": "4"})

    agent = GraphAgent(
        model_client=model,
        tool_executor=tools,
        registry=FakeRegistry(),
        context_provider=FakeContextProvider(),
        message_store=message_store,
        event_bus=None,
        event_factory=None,
    )

    result = agent.run("What is 2+2?")

    assert result.output == "The answer is 4."
    assert result.status == "completed"
    assert len(model.calls) == 2          # 1st: tool call, 2nd: answer
    assert len(tools.calls) == 1          # tool ran once
    assert tools.calls[0].function.name == "calculator"
    assert tools.calls[0].function.arguments == {"expr": "2+2"}
    assert len(message_store.tool_messages) == 1
    assert message_store.tool_messages[0]["content"] == "4"

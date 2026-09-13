"""Unit tests for the canonical agent nodes (improvement #1: agent as node).

Tests each node in isolation against fake model/tool dependencies, plus
the run-reuse property of GraphAgent (graph built once, state isolated).
"""

import types

import pytest

from graph.state import GraphState
from mini_agent.event_bus import EventBus
from mini_agent.event_factory import EventFactory
from mini_agent.graph_agent import GraphAgent
from mini_agent.nodes import (
    DECISION,
    FINAL_OUTPUT,
    RUN_ID,
    TOOL_CALLS_LOG,
    USER_INPUT,
    AgentNode,
    AnswerNode,
    DecisionRouter,
    ToolNode,
)
from mini_agent.tool_calls import tool_call_arguments, tool_call_name
from mini_agent.tool_result import ToolResult

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class OpenAIToolCall:
    def __init__(self, name, arguments, call_id="call_1"):
        self.function = FakeFunction(name, arguments)
        self.id = call_id


class CustomToolCall:
    def __init__(self, name, arguments, call_id="call_1"):
        self.name = name
        self.arguments = arguments
        self.id = call_id


class FakeResponse:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeModelClient:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def generate(self, messages, tools):
        self.calls.append({"messages": list(messages), "tools": tools})
        return self._scripted.pop(0)


class FakeContextProvider:
    def build(self, user_input):
        self.last_input = user_input
        return types.SimpleNamespace(
            messages=[{"role": "user", "content": user_input}]
        )


class FakeRegistry:
    def schemas(self):
        return [{"type": "function", "function": {"name": "calculator"}}]


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


class FakeToolExecutor:
    def __init__(self, results_by_name):
        self._results = results_by_name
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        name = tool_call_name(tool_call)
        return ToolResult(
            tool_call_id=tool_call.id,
            name=name,
            arguments=tool_call_arguments(tool_call),
            content=self._results.get(name, "no result"),
            success=True,
        )


class EventRecorder:
    """EventBus handler that keeps the full Event objects."""

    def __init__(self):
        self.events = []

    def handle(self, event):
        self.events.append(event)

    @property
    def kinds(self):
        return [e.event_type for e in self.events]

    @property
    def run_ids(self):
        return {e.run_id for e in self.events}


def make_state(user_input="hi", run_id="run-1"):
    state = GraphState()
    state.set(USER_INPUT, user_input)
    state.set(RUN_ID, run_id)
    return state


# ---------------------------------------------------------------------------
# Shared tool-call normalizer
# ---------------------------------------------------------------------------

def test_tool_call_name_accepts_both_shapes():
    assert tool_call_name(OpenAIToolCall("calc", {})) == "calc"
    assert tool_call_name(CustomToolCall("calc", {})) == "calc"


def test_tool_call_name_raises_without_name_and_honors_default():
    class Empty:
        pass

    with pytest.raises(ValueError):
        tool_call_name(Empty())

    assert tool_call_name(Empty(), default="<unknown>") == "<unknown>"


# ---------------------------------------------------------------------------
# AgentNode
# ---------------------------------------------------------------------------

def test_agent_node_writes_tool_decision_and_persists_assistant():
    rec, event_bus, factory = EventRecorder(), EventBus(), EventFactory()
    event_bus.subscribe(rec)
    store = FakeMessageStore()

    node = AgentNode(
        "think",
        model_client=FakeModelClient(
            [FakeResponse(tool_calls=[OpenAIToolCall("calculator", {"expr": "2+2"})])]
        ),
        context_provider=FakeContextProvider(),
        registry=FakeRegistry(),
        message_store=store,
        event_bus=event_bus,
        event_factory=factory,
    )

    state = node.execute(make_state())

    decision = state.get(DECISION)
    assert decision["type"] == "tool"
    assert len(decision["calls"]) == 1
    assert len(store.assistant_messages) == 1
    assert rec.kinds == ["step_started", "model_called", "model_completed"]
    # run_id came from state, not from a constructor argument
    assert rec.run_ids == {"run-1"}


def test_agent_node_writes_answer_decision():
    node = AgentNode(
        "think",
        model_client=FakeModelClient([FakeResponse(content="The answer is 4.")]),
        context_provider=FakeContextProvider(),
        registry=FakeRegistry(),
    )

    state = node.execute(make_state())

    assert state.get(DECISION) == {"type": "answer", "content": "The answer is 4."}


def test_agent_node_runs_without_tracing_or_store():
    node = AgentNode(
        "think",
        model_client=FakeModelClient([FakeResponse(content="ok")]),
        context_provider=FakeContextProvider(),
        registry=FakeRegistry(),
    )

    state = node.execute(make_state())

    assert state.get(DECISION)["content"] == "ok"


# ---------------------------------------------------------------------------
# ToolNode
# ---------------------------------------------------------------------------

def test_tool_node_executes_calls_appends_log_and_persists():
    rec, event_bus, factory = EventRecorder(), EventBus(), EventFactory()
    event_bus.subscribe(rec)
    store = FakeMessageStore()
    executor = FakeToolExecutor({"calculator": "4", "clock": "noon"})

    node = ToolNode(
        "act",
        tool_executor=executor,
        message_store=store,
        event_bus=event_bus,
        event_factory=factory,
    )

    state = make_state()
    state.set(DECISION, {
        "type": "tool",
        "calls": [
            OpenAIToolCall("calculator", {"expr": "2+2"}, call_id="c1"),
            CustomToolCall("clock", {}, call_id="c2"),
        ],
    })

    state = node.execute(state)

    assert len(executor.calls) == 2
    log = state.get(TOOL_CALLS_LOG)
    assert [entry["name"] for entry in log] == ["calculator", "clock"]
    assert [m["call_id"] for m in store.tool_messages] == ["c1", "c2"]
    assert rec.kinds == [
        "tool_started", "tool_completed",
        "tool_started", "tool_completed",
    ]
    assert rec.run_ids == {"run-1"}


def test_tool_node_noop_on_answer_decision():
    executor = FakeToolExecutor({})

    node = ToolNode("act", tool_executor=executor)

    state = make_state()
    state.set(DECISION, {"type": "answer", "content": "done"})

    state = node.execute(state)

    assert executor.calls == []
    assert state.get(TOOL_CALLS_LOG) is None


def test_tool_node_links_completed_to_started_event():
    rec, event_bus, factory = EventRecorder(), EventBus(), EventFactory()
    event_bus.subscribe(rec)

    node = ToolNode(
        "act",
        tool_executor=FakeToolExecutor({"calculator": "4"}),
        event_bus=event_bus,
        event_factory=factory,
    )

    state = make_state()
    state.set(DECISION, {"type": "tool", "calls": [OpenAIToolCall("calculator", {})]})
    node.execute(state)

    started, completed = rec.events[0], rec.events[1]
    assert started.event_type == "tool_started"
    assert completed.event_type == "tool_completed"
    assert completed.parent_event_id == started.event_id


# ---------------------------------------------------------------------------
# AnswerNode + DecisionRouter
# ---------------------------------------------------------------------------

def test_answer_node_writes_final_output():
    node = AnswerNode()

    state = make_state()
    state.set(DECISION, {"type": "answer", "content": "42"})

    state = node.execute(state)

    assert state.get(FINAL_OUTPUT) == "42"


def test_decision_router_routes_on_decision_type():
    router = DecisionRouter()

    tool_state = make_state()
    tool_state.set(DECISION, {"type": "tool", "calls": []})
    assert router.route(tool_state) == "tool"

    answer_state = make_state()
    answer_state.set(DECISION, {"type": "answer", "content": "hi"})
    assert router.route(answer_state) == "answer"

    assert router.route(make_state()) == "answer"


# ---------------------------------------------------------------------------
# GraphAgent reuse across runs
# ---------------------------------------------------------------------------

def _make_agent(script):
    store = FakeMessageStore()
    agent = GraphAgent(
        model_client=FakeModelClient(list(script)),
        tool_executor=FakeToolExecutor({"calculator": "4"}),
        registry=FakeRegistry(),
        context_provider=FakeContextProvider(),
        message_store=store,
    )
    return agent, store


def test_graph_agent_reuses_graph_and_isolates_runs():
    agent, _store = _make_agent([
        FakeResponse(content="first answer"),
        FakeResponse(content="second answer"),
    ])

    graph_before = agent._graph
    run_1 = agent.run("hello")

    assert agent._graph is graph_before  # no per-run rebuild
    assert run_1.output == "first answer"

    run_2 = agent.run("hello again")

    assert run_2.output == "second answer"
    assert run_2.tool_calls == []  # no state bleed from run 1


def test_graph_agent_publishes_run_lifecycle_events():
    rec, event_bus, factory = EventRecorder(), EventBus(), EventFactory()
    event_bus.subscribe(rec)

    agent = GraphAgent(
        model_client=FakeModelClient([FakeResponse(content="hi there")]),
        tool_executor=FakeToolExecutor({}),
        registry=FakeRegistry(),
        context_provider=FakeContextProvider(),
        message_store=FakeMessageStore(),
        event_bus=event_bus,
        event_factory=factory,
    )

    result = agent.run("hello")

    assert result.status == "completed"
    assert rec.kinds[0] == "run_started"
    assert rec.kinds[-1] == "run_completed"
    # every event belongs to the same run
    assert len(rec.run_ids) == 1

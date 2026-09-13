"""Tests for the eval harness scoring, using fakes (no LLM, no API key)."""

from mini_agent.eval.case import EvalCase
from mini_agent.eval.runner import Evaluator, ToolRecorder
from mini_agent.event_bus import EventBus
from mini_agent.event_factory import EventFactory


class FakeAgent:
    """Publishes tool_started events, then returns a canned answer."""

    def __init__(self, output, tool_names, event_bus, event_factory):
        self.output = output
        self._tool_names = tool_names
        self._event_bus = event_bus
        self._event_factory = event_factory

    def run(self, user_input):
        for step, name in enumerate(self._tool_names):
            self._event_bus.publish(
                self._event_factory.tool_started("run_fake", name, step=step)
            )
        return self.output


def make_agent_factory(output, tool_names):
    def factory():
        event_bus = EventBus()
        agent = FakeAgent(output, tool_names, event_bus, EventFactory())
        return agent, event_bus

    return factory


def test_tool_recorder_captures_tool_started_names():
    recorder = ToolRecorder()
    event_bus = EventBus()
    event_bus.subscribe(recorder)
    factory = EventFactory()

    event_bus.publish(factory.tool_started("r1", "calculator", step=1))
    event_bus.publish(factory.tool_completed("r1", "calculator", True, step=1))
    event_bus.publish(factory.tool_started("r1", "save_note", step=2))

    assert recorder.tool_names == ["calculator", "save_note"]


def test_eval_passes_on_answer_and_tool_match():
    evaluator = Evaluator(make_agent_factory("The answer is 4", ["calculator"]))
    case = EvalCase(
        name="ok",
        user_input="what is 2+2?",
        expected_answer="4",
        expected_tools=["calculator"],
    )

    result = evaluator.evaluate(case)

    assert result.passed is True
    assert result.actual_tools == ["calculator"]


def test_eval_fails_on_tool_mismatch():
    evaluator = Evaluator(make_agent_factory("The answer is 4", ["calculator"]))
    case = EvalCase(
        name="wrong_tools",
        user_input="what is 2+2?",
        expected_answer="4",
        expected_tools=["save_note"],
    )

    result = evaluator.evaluate(case)

    assert result.passed is False
    assert result.tools is False
    assert result.answer is True


def test_eval_answer_check_is_case_insensitive_substring():
    evaluator = Evaluator(make_agent_factory("SABR is the model.", []))
    case = EvalCase(name="ci", user_input="?", expected_answer="sabr")

    result = evaluator.evaluate(case)

    assert result.answer is True


def test_eval_agent_exception_is_recorded_as_failure():
    def boom_factory():
        class Boom:
            def run(self, user_input):
                raise RuntimeError("llm down")

        event_bus = EventBus()
        return Boom(), event_bus

    evaluator = Evaluator(boom_factory)
    case = EvalCase(name="boom", user_input="?")

    result = evaluator.evaluate(case)

    assert result.passed is False
    assert "llm down" in result.error

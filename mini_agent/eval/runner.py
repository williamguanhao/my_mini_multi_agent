"""Eval harness on top of the current Event/EventBus layer.

Each case runs against a freshly built agent (the factory returns a new
(agent, event_bus) pair so sessions stay isolated). Tool usage is captured
from `tool_started` events; scoring is:

  - answer: case.expected_answer substring match, case-insensitive
  - tools:  exact ordered match of tool_started payloads
"""

from dataclasses import dataclass, field


@dataclass
class CaseResult:
    name: str
    answer: bool
    tools: bool
    passed: bool
    output: str | None = None
    actual_tools: list[str] = field(default_factory=list)
    error: str | None = None


class ToolRecorder:
    """EventBus handler capturing tool names from tool_started events."""

    def __init__(self):
        self.tool_names: list[str] = []

    def handle(self, event):
        if event.event_type == "tool_started":
            self.tool_names.append(event.payload.get("tool"))


class Evaluator:

    def __init__(self, agent_factory):
        # agent_factory: callable -> (agent, event_bus), fresh per case
        self._agent_factory = agent_factory

    def evaluate(self, case) -> CaseResult:
        agent, event_bus = self._agent_factory()
        recorder = ToolRecorder()
        event_bus.subscribe(recorder)

        try:
            answer = agent.run(case.user_input)
        except Exception as e:
            return CaseResult(
                name=case.name,
                answer=False,
                tools=False,
                passed=False,
                error=str(e),
            )

        answer_ok = self.check_answer(case, answer)
        tools_ok = self.check_tools(case, recorder.tool_names)

        return CaseResult(
            name=case.name,
            answer=answer_ok,
            tools=tools_ok,
            passed=answer_ok and tools_ok,
            output=answer,
            actual_tools=list(recorder.tool_names),
        )

    def check_answer(self, case, answer) -> bool:

        if case.expected_answer is None:
            return True

        if answer is None:
            return False

        return (
            case.expected_answer.lower()
            in answer.lower()
        )

    def check_tools(self, case, actual_tools) -> bool:

        if not case.expected_tools:
            return True

        return list(actual_tools) == list(case.expected_tools)

    def run_all(self, cases) -> list[CaseResult]:

        results = []

        for case in cases:

            print(f"\nRunning: {case.name}")

            result = self.evaluate(case)

            status = (
                "PASS"
                if result.passed
                else "FAIL"
            )

            detail = ""
            if not result.passed:
                detail = (
                    f" (tools={result.actual_tools},"
                    f" output={result.output!r},"
                    f" error={result.error!r})"
                )

            print(f"{case.name}: {status}{detail}")

            results.append(result)

        self.print_summary(results=results)

        return results

    @staticmethod
    def print_summary(results):

        passed = sum(
            result.passed
            for result in results
        )

        total = len(results)

        print("\n" + "=" * 40)
        print("EVALUATION SUMMARY")
        print("=" * 40)

        print(
            f"Passed: {passed}/{total}"
        )

        print(
            f"Failed: {total - passed}/{total}"
        )

        if total:
            print(
                f"Score: {passed / total:.1%}"
            )

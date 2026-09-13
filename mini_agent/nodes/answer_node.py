"""AnswerNode — extracts the final answer from the current decision."""

from graph.node import Node
from graph.state import GraphState

from .state_keys import DECISION, FINAL_OUTPUT


class AnswerNode(Node):

    def __init__(self, name: str = "answer"):
        super().__init__(name)

    def execute(self, state: GraphState) -> GraphState:
        decision = state.get(DECISION) or {}
        state.set(FINAL_OUTPUT, decision.get("content", ""))
        return state

"""DecisionRouter — routes on the decision written by AgentNode.

Returns the route name "tool" or "answer"; the graph maps these onto
node targets via add_conditional_edges().
"""

from graph.router import Router
from graph.state import GraphState

from .state_keys import DECISION


class DecisionRouter(Router):

    def route(self, state: GraphState) -> str:
        decision = state.get(DECISION) or {}
        return "tool" if decision.get("type") == "tool" else "answer"

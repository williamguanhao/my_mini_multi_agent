from ..node import Node
from ..state import GraphState

class AgentNode(Node):

    def __init__(
            self, 
            name,
            agent,
            ):
        super().__init__(name)
        self.agent = agent

    def execute(self, state: GraphState) -> GraphState:
        result = self.agent.complete(state)

        state.set(
            "agent_result",
            result,
        )

        return state
    
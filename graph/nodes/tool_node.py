from ..node import Node
from ..state import GraphState


class ToolNode(Node):

    def __init__(
        self,
        name,
        tool_executor,
    ):
        super().__init__(name)
        self.tool_executor = tool_executor

    def execute(
        self,
        state: GraphState,
    ) -> GraphState:

        agent_result = state.get(
            "agent_result"
        )

        tool_name = agent_result[
            "tool_name"
        ]

        arguments = agent_result[
            "arguments"
        ]

        result = (
            self.tool_executor.execute(
                tool_name,
                arguments,
            )
        )

        state.set(
            "tool_result",
            result,
        )

        return state
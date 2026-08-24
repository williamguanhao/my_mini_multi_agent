from ..router import Router
from ..state import GraphState


class AgentRouter(Router):

    def route(
        self,
        state: GraphState,
    ) -> str:

        result = state.get(
            "agent_result"
        )

        if result is None:
            raise RuntimeError(
                "Agent result is missing."
            )

        if result["type"] == "tool_call":
            return "tool"

        if result["type"] == "final":
            return "end"

        raise RuntimeError(
            f"Unknown agent result type: "
            f"{result['type']}"
        )
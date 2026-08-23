from abc import ABC, abstractmethod
from dataclasses import dataclass

from .state import GraphState

class Router(ABC):
    """
    Determines which route should be taken
    based on the current graph state.
    """

    @abstractmethod
    def route(
        self,
        state: GraphState,
    ) -> str:

        raise NotImplementedError


class FunctionRouter(Router):

    def __init__(
        self,
        function,
    ):
        self.function = function

    def route(
        self,
        state: GraphState,
    ) -> str:

        result = self.function(state)

        if not isinstance(result, str):
            raise TypeError(
                "Router must return a string route."
            )

        return result


class AgentRouter(Router):

    def route(
        self,
        state: GraphState,
    ) -> str:

        if state.get("done"):
            return "end"

        if state.get("tool_required"):
            return "tool"

        return "end"

@dataclass
class Route:
    name: str
    target: str
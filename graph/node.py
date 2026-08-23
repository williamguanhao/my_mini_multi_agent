from abc import ABC, abstractmethod
from typing import Any

from .state import GraphState

class Node(ABC):

    def __init__(self, name:str):
        self.name = name

    @abstractmethod
    def execute(
            self,
            state: GraphState
    ) -> GraphState:
        raise NotImplementedError

class AgentNode(Node):

    def execute(
            self,
            state:GraphState,
    ) -> GraphState:

        if state.get("tool_result"):

            state.set(
                "final_answer",
                "I have enough information.",
            )

            state.set(
                "Done",
                True,
            )

        else:

            state.set(
                "tool_required",
                True,
            )

        return state

class ToolNode(Node):

    def execute(
            self, 
            state: GraphState
            ) -> GraphState:
        
        state.set(
            "tool_result",
            "search result",
        )

        state.set(
            "tool_required",
            False,
        )

        return state
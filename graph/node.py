from abc import ABC, abstractmethod

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

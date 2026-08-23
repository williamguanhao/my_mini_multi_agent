from dataclasses import dataclass
from typing import Callable

@dataclass
class Edge:
    source: str
    target: str
    route: str | None = None,
    name: str | None = None
    condition: Callable | None = None

    def should_traverse(
            self,
            state,
    ) -> bool:

        if self.condition is None:
            return True

        return self.condition(state)
    
    @property
    def label(self):

        return (
            self.name
            or f"{self.source}->{self.target}"
        )
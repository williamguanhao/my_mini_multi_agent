from dataclasses import dataclass, field
from typing import Any
from copy import deepcopy

@dataclass
class GraphState:

    values: dict[str, Any] = field(
        default_factory=dict
    )

    current_node: str | None = None

    step: int = 0

    finished: bool = False

    error: Exception | None = None

    def get(
            self,
            key: str,
            default=None,
    ):
        return self.values.get(
            key,
            default,
        )

    def set(
            self,
            key: str,
            value: Any
    ):
        self.values[key]=value

    def snapshot(self) -> dict:

        return {
            "values": deepcopy(
                self.values
            ),
            "current_node": self.current_node,
            "step": self.step,
            "finished": self.finished,
            "error": (
                str(self.error)
                if self.error
                else None
            ),
        }
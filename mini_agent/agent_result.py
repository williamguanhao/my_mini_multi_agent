from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    output: str | None = None

    status: str = "completed"

    iterations: int = 0

    tool_calls: list[dict[str, Any]] = field(
        default_factory=list
    )

    state: Any | None = None

    error: Exception | None = None

    @property
    def success(self) -> bool:
        return self.status == "completed"
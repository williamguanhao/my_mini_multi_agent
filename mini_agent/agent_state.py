from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentState:
    user_input: str
    step: int = 0
    finished: bool = False
    final_output: str | None = None

    tool_calls: list[dict[str, Any]] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    
    error: Exception | None = None
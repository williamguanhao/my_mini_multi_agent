from dataclasses import dataclass
from typing import Any

@dataclass
class AgentState:
    user_input: str
    step: int = 0
    finished: bool = False
    final_output: str | None = None
    error: Exception | None = None
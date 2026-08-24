from dataclasses import dataclass
from typing import Any


@dataclass
class AgentDecision:

    type: str

    tool_name: str | None = None

    arguments: dict[str, Any] | None = None

    content: str | None = None
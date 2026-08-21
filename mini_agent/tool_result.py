from dataclasses import dataclass
from typing import Any

@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    arguments: dict[str, Any]

    content: str
    success: bool = True


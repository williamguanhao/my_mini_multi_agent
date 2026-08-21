from dataclasses import dataclass
from typing import Any

@dataclass
class ModelResponse:
    content: str | None
    tool_calls: list[Any]


class ModelClient:

    def __init__(self, gateway):
        self.gateway = gateway

    def generate(
            self,
            messages,
            tools,
        ) -> ModelResponse:

        response = self.gateway.chat(
            messages,
            tools
        )

        return ModelResponse(
            content=response.content,
            tool_calls=response.tool_calls or [],
        )
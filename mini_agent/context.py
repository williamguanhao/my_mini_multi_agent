from dataclasses import dataclass
from typing import Any

@dataclass
class AgentContext:
    messages: list[Any]


class ContextProvider:

    def __init__(
            self,
            session,
            retriever
            ):
        self.session = session
        self.retriever = retriever

    def build(
            self,
            user_input: str
        ) -> AgentContext:
        messages = self.retriever.retrieve(
            self.session,
            user_input
        )

        return AgentContext(messages=messages)
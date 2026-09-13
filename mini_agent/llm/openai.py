from openai import OpenAI

from .base import (
    BaseLLM,
    LLMResponse,
    ToolCall,
)


class OpenAILLM(BaseLLM):

    def __init__(
        self,
        api_key,
        model,
    ):

        self.client = OpenAI(
            api_key=api_key,
        )

        self.model = model

    def ask(self, messages, tools=None):

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )

        message = response.choices[0].message

        tool_calls = []

        if message.tool_calls:

            for call in message.tool_calls:

                tool_calls.append(
                    ToolCall(
                        id=call.id,
                        name=call.function.name,
                        arguments=call.function.arguments,
                    )
                )

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
        )
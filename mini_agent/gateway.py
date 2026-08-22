import time
class Gateway:

    def __init__(self, llm):
        self.llm = llm

    def chat(self, messages, tools = None):

        response = self.llm.ask(
            messages=messages,
            tools=tools
        )

        return response
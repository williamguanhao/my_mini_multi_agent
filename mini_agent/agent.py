import json
from .registry import ToolRegistry
from .session import Session
from .runtime import Runtime
from .retrieval import Retriever
from .gateway import Gateway
from .tracer import Tracer
from .agent_loop import AgentLoop
SYSTEM = """
    You are mini_agent, a helpful personal assistant.

    Be concise.
    Be honest.
    Do not claim to have performed actions you did not perform.
    When you are unsure about something, say "I don't know" or "I'm not sure".
"""
class Agent:

    def __init__(
            self, 
            gateway: Gateway,
            registry: ToolRegistry,
            session:Session,
            runtime:Runtime,
            retriever:Retriever,
            tracer = None,
            system_prompt:str=SYSTEM
    ):
        self.loop = AgentLoop(
            gateway=gateway,
            registry=registry,
            session=session,
            runtime=runtime,
            retriever=retriever,
            tracer=tracer,
            system_prompt=system_prompt
        )

    def run(self, user_input:str, max_steps=10) -> str:
        return self.loop.run(
            user_input=user_input,
            max_steps=max_steps,
        )




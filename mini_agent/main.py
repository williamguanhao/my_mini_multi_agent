from .tools.time import GetTimeTool
from .tools.save_note import SaveNoteTool
from .tools.calculator import CalculatorTool
from .tools.read_notes import ReadNotesTool
from .agent import Agent
from .registry import ToolRegistry
from .llm.minimax import MiniMaxLLM
from .session import Session
from .runtime import Runtime
from .memory import SQLiteMemory
from .config import API_KEY, MODEL, BASE_URL
from .retrieval import Retriever
from .gateway import Gateway
from .tracer import Tracer
SYSTEM = """
    You are mini_agent, a helpful personal assistant.

    Be concise.
    Be honest.
    Do not claim to have performed actions you did not perform.
    When you are unsure about something, say "I don't know" or "I'm not sure".
"""

def main():

    memory = SQLiteMemory()

    session = Session(session_id="multi_demo_session", memory=memory)

    tracer = Tracer()

    llm = MiniMaxLLM(
        api_key=API_KEY,
        model=MODEL)

    gateway = Gateway(llm=llm, tracer=tracer)

    tools = [
        GetTimeTool(),
        SaveNoteTool(memory=memory, session_id=session.session_id),
        CalculatorTool(),
        ReadNotesTool(memory=memory, session_id=session.session_id)
    ]

    registry = ToolRegistry(tools)

    runtime = Runtime(registry, tracer=tracer)

    retriever = Retriever(memory=memory, recent_limit=20, relevent_limit=10)

    agent = Agent(
        gateway=gateway, 
        registry=registry,
        session=session,
        runtime=runtime,
        retriever=retriever,
        tracer=tracer,
        system_prompt=SYSTEM
    )

    # -------------------------
    # Chat loop
    # -------------------------
    
    while True:
        user_input = input("you > ")

        if user_input in {"quit", "exit"}:
            break

        answer = agent.run(user_input)

        print(f"mini_agent > {answer}")


if __name__ == "__main__":
    main()
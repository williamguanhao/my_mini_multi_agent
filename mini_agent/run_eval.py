from mini_agent.eval.cases import CASES
from mini_agent.eval.runner import Evaluator
from mini_agent.tracer import Tracer
from mini_agent.agent import Agent
from mini_agent.gateway import Gateway
from mini_agent.llm.minimax import MiniMaxLLM
from mini_agent.registry import ToolRegistry
from mini_agent.memory import SQLiteMemory
from mini_agent.session import Session
from mini_agent.runtime import Runtime
from mini_agent.retrieval import Retriever
from mini_agent.tools.time import GetTimeTool
from mini_agent.tools.save_note import SaveNoteTool
from mini_agent.tools.calculator import CalculatorTool
from mini_agent.tools.read_notes import ReadNotesTool
from mini_agent.config import API_KEY, MODEL, BASE_URL

def build_agent():
    SYSTEM = """
    You are mini_agent, a helpful personal assistant.

    Be concise.
    Be honest.
    Do not claim to have performed actions you did not perform.
    When you are unsure about something, say "I don't know" or "I'm not sure".
    """
    tracer = Tracer()

    memory = SQLiteMemory()

    session = Session(session_id="demo_session", memory=memory)

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
        )
    return agent

def main():
    agent = build_agent()
    evaluator = Evaluator()

    evaluator.run_all(
        agent=agent, 
        cases=CASES)

if __name__ == "__main__":
    main()
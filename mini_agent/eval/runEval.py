from mini_agent.eval.case import EvalCase
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

cases = [

    EvalCase(
        name="calculator",
        user_input="What is 123 * 456?",
        expected_answer="56088",
        expected_tools=["calculator"],
    ),

    EvalCase(
        name="get_time",
        user_input="What time is it?",
        expected_tools=["get_time"],
    ),

    EvalCase(
        name="save_note",
        user_input="Remember that my favorite model is SABR.",
        expected_tools=["save_note"],
    ),

    EvalCase(
        name="no_tool",
        user_input="Explain what Black-Scholes is.",
        expected_tools=[],
    ),
]
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

evaluator = Evaluator()

for case in cases:
    answer = agent.run(
        case.user_input
    )

    result = evaluator.evaluate(
        case=case,
        answer=answer,
        trace=tracer.get_events(),
    )

    print(result)
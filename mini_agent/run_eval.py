"""Entry point for the eval harness: `agent-eval`.

Builds a fresh agent stack per case (isolated temp memory DB), runs the
loop engine against the real LLM, and scores answers + tool sequences.
Requires MINIMAX_API_KEY in the environment; never runs in CI.
"""

import tempfile
from pathlib import Path

from .agent import Agent
from .config import API_KEY, MODEL
from .context import ContextProvider
from .eval.cases import CASES
from .eval.runner import Evaluator
from .event_bus import EventBus
from .event_factory import EventFactory
from .gateway import Gateway
from .llm.minimax import MiniMaxLLM
from .memory import SQLiteMemory
from .message_store import MessageStore
from .model import ModelClient
from .prompts import SYSTEM
from .registry import ToolRegistry
from .retrieval import Retriever
from .runtime import Runtime
from .session import Session
from .tool_executor import ToolExecutor
from .tools.calculator import CalculatorTool
from .tools.read_notes import ReadNotesTool
from .tools.save_note import SaveNoteTool
from .tools.time import GetTimeTool

_eval_run_counter = 0


def build_case_agent():
    """Build a fresh (agent, event_bus) pair with an isolated memory DB."""
    global _eval_run_counter
    _eval_run_counter += 1

    tmp_dir = tempfile.mkdtemp(prefix="mini_agent_eval_")
    memory = SQLiteMemory(db_path=str(Path(tmp_dir) / "memory.db"))
    session = Session(
        session_id=f"eval_run_{_eval_run_counter}",
        memory=memory,
    )

    retriever = Retriever(memory=memory, recent_limit=20, relevent_limit=10)
    context_provider = ContextProvider(
        session=session,
        retriever=retriever,
        default_system_prompt=SYSTEM,
    )
    message_store = MessageStore(session=session)

    llm = MiniMaxLLM(api_key=API_KEY, model=MODEL)
    gateway = Gateway(llm=llm)
    model_client = ModelClient(gateway=gateway)

    tools = [
        GetTimeTool(),
        SaveNoteTool(memory=memory, session_id=session.session_id),
        CalculatorTool(),
        ReadNotesTool(memory=memory, session_id=session.session_id),
    ]
    registry = ToolRegistry(tools)
    runtime = Runtime(registry=registry)
    tool_executor = ToolExecutor(runtime=runtime)

    event_bus = EventBus()

    agent = Agent(
        context_provider=context_provider,
        model_client=model_client,
        tool_executor=tool_executor,
        registry=registry,
        session=session,
        message_store=message_store,
        event_bus=event_bus,
        event_factory=EventFactory(),
    )

    return agent, event_bus


def main():
    evaluator = Evaluator(agent_factory=build_case_agent)
    evaluator.run_all(cases=CASES)


if __name__ == "__main__":
    main()

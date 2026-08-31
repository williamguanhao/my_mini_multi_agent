import argparse
import sys

from .tools.time import GetTimeTool
from .tools.save_note import SaveNoteTool
from .tools.calculator import CalculatorTool
from .tools.read_notes import ReadNotesTool
from .tools.get_yfinance_data import GetYfOHLCVTool
from .agent import Agent
from .graph_agent import GraphAgent
from .registry import ToolRegistry
from .llm.minimax import MiniMaxLLM
from .session import Session
from .runtime import Runtime
from .memory import SQLiteMemory
from .config import API_KEY, MODEL, BASE_URL
from .retrieval import Retriever
from .gateway import Gateway
from .context import ContextProvider
from .model import ModelClient
from .mcp import MCPClient
from .tool_executor import ToolExecutor
from .message_store import MessageStore
from .event_bus import EventBus
from .console_tracer import ConsoleTracer
from .json_tracer import JsonTracer
from .sqlite_trace_store import SQLiteTraceStore
from .trace_collector import TraceCollector
from .event_factory import EventFactory
SYSTEM = """
    You are mini_agent, a helpful personal assistant.

    Be concise.
    Be honest.
    Do not claim to have performed actions you did not perform.
    When you are unsure about something, say "I don't know" or "I'm not sure".
"""

def setup_mcp_clients(registry):
    """Start MCP server subprocesses, discover their tools, register them.

    MCPClient owns a BackgroundLoop (daemon thread running an event loop).
    All async MCP work happens on that loop, so stdio streams and anyio
    cancel scopes stay coherent across multiple call_tool() invocations.
    Returns the list of started clients.
    """
    clients = [
        MCPClient(
            command=sys.executable,
            args=["-m", "server"],
            cwd="mcp_servers/yfinance",
        ),
        MCPClient(
            command=sys.executable,
            args=["-m", "server"],
            cwd="mcp_servers/fred",
        ),
    ]
    started = []
    for client in clients:
        try:
            client.connect()
            tools = client.list_tools()
            for tool in tools:
                registry.register(tool)
            print(f"[mcp] registered {len(tools)} tools from {client._command}")
            started.append(client)
        except Exception as e:
            print(f"[mcp] failed: {e}")
    return started


def teardown_mcp_clients(clients):
    for client in clients:
        try:
            client.disconnect()
        except Exception:
            pass


def main():

    parser = argparse.ArgumentParser(
        description="mini_agent CLI",
    )
    parser.add_argument(
        "--engine",
        choices=("loop", "graph"),
        default="loop",
        help="Agent engine: 'loop' (default) uses AgentLoop; "
             "'graph' uses the graph-based GraphAgent.",
    )
    args = parser.parse_args()

    memory = SQLiteMemory()

    session = Session(session_id="multi_demo_session", memory=memory)

    retriever = Retriever(memory=memory, recent_limit=20, relevent_limit=10)
    
    context_providor = ContextProvider(session=session, retriever=retriever, default_system_prompt=SYSTEM)

    message_store = MessageStore(session=session)

    llm = MiniMaxLLM(
        api_key=API_KEY,
        model=MODEL)

    gateway = Gateway(llm=llm)

    model_client = ModelClient(gateway=gateway)

    tools = [
        GetTimeTool(),
        SaveNoteTool(memory=memory, session_id=session.session_id),
        CalculatorTool(),
        ReadNotesTool(memory=memory, session_id=session.session_id),
    ]

    registry = ToolRegistry(tools)

    # Connect MCP servers and register their tools alongside the built-ins.
    mcp_clients = setup_mcp_clients(registry)
    try:
        runtime = Runtime(registry=registry)

        tool_executor = ToolExecutor(runtime=runtime)

        event_bus = EventBus()

        trace_store = SQLiteTraceStore("traces.db")

        trace_collector = TraceCollector(trace_store)

        console_tracer = ConsoleTracer()

        json_tracer = JsonTracer()

        event_bus.subscribe(trace_collector)

        event_bus.subscribe(console_tracer)

        event_bus.subscribe(json_tracer)

        event_factory = EventFactory()

        common_kwargs = dict(
            context_provider=context_providor,
            model_client=model_client,
            tool_executor=tool_executor,
            registry=registry,
            message_store=message_store,
            event_bus=event_bus,
            event_factory=event_factory,
        )

        if args.engine == "loop":
            agent = Agent(**common_kwargs, session=session)
        else:
            agent = GraphAgent(**common_kwargs)

        # -------------------------
        # Chat loop
        # -------------------------

        while True:
            user_input = input("you > ")

            if user_input in {"quit", "exit"}:
                break

            if args.engine == "loop":
                try:
                    answer = agent.run(user_input)
                except Exception as e:
                    answer = f"[error] {e}"
            else:
                result = agent.run(user_input)
                if result.status == "error":
                    answer = f"[error] {result.error}"
                else:
                    answer = result.output or ""

            print(f"mini_agent > {answer}")
    finally:
        teardown_mcp_clients(mcp_clients)


if __name__ == "__main__":
    main()
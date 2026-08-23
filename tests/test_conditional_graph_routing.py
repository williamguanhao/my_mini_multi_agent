from ..graph.node import AgentNode, ToolNode
from ..graph.graph import Graph
from ..graph.router import AgentRouter
from ..graph.state import GraphState 

graph = Graph()

graph.add_node(
    "agent",
    AgentNode("agent"),
)

graph.add_node(
    "tool",
    ToolNode("tool"),
)

graph.add_edge(
    Graph.START,
    "agent",
    "start_run",
)

graph.add_conditional_edges(
    "agent",
    AgentRouter(),
    {
        "tool": "tool",
        "end": Graph.END,
    },
)

graph.add_edge(
    "tool",
    "agent",
    "back_to_agent"
)
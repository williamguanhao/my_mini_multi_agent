from .graph import Graph
from .nodes.agent_node import AgentNode
from .nodes.tool_node import ToolNode
from .nodes.agent_router import AgentRouter

class AgentGraph:

    def __init__(
            self,
            agent,
            tool_executor
            ):
        self.graph=Graph()

        self.graph.add_node(
            "agent",
            AgentNode(
                "agent",
                agent,
            )
        )

        self.graph.add_node(
            "tool",
            ToolNode(
                "tool",
                tool_executor,
            )
        )

        # Thought → Action → Observation
        
        self.graph.add_edge(
            Graph.START,
            "agent"
        )

        self.graph.add_conditional_edges(
            "agent",
            AgentRouter(),
            {"tool": "tool",
             "end": Graph.END,
            }
        )

        self.graph.add_edge(
            "tool",
            "agent",
        )
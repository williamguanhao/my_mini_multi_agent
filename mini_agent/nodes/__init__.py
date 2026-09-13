"""Canonical agent nodes for the graph engine (improvement #1).

These live in `mini_agent/`, not `graph/`: the engine stays
LLM-agnostic (the narrow waist), while model-aware capability nodes
sit at the edge — same split as langgraph's `graph` vs `prebuilt`.
"""

from .agent_node import AgentNode
from .answer_node import AnswerNode
from .decision_router import DecisionRouter
from .state_keys import (
    DECISION,
    FINAL_OUTPUT,
    RUN_ID,
    TOOL_CALLS_LOG,
    USER_INPUT,
)
from .tool_node import ToolNode

__all__ = [
    "AgentNode",
    "AnswerNode",
    "DecisionRouter",
    "ToolNode",
    "DECISION",
    "FINAL_OUTPUT",
    "RUN_ID",
    "TOOL_CALLS_LOG",
    "USER_INPUT",
]

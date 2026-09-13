"""Canonical graph-state keys shared by the agent nodes.

These constants are the contract between nodes: every node reads and
writes only these keys. A small step toward fully typed channels (#2).
"""

RUN_ID = "run_id"
"""Populated once per run by the agent (GraphAgent/runner) before execution."""

USER_INPUT = "user_input"
"""The user message that started the run."""

DECISION = "decision"
"""Written by AgentNode: {"type": "tool", "calls": [...]} or {"type": "answer", "content": str}."""

TOOL_CALLS_LOG = "tool_calls_log"
"""Appended to by ToolNode: one dict per executed tool call (for AgentResult)."""

FINAL_OUTPUT = "final_output"
"""Written by AnswerNode: the agent's final answer text."""

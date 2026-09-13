"""Shared tool-call shape normalization.

Tool calls arrive in two shapes depending on the provider:

- OpenAI-style:   tool_call.function.name / tool_call.function.arguments
- Custom style:   tool_call.name / tool_call.arguments

Every consumer (Runtime, AgentLoop, graph nodes) must accept both, so the
logic lives here exactly once.
"""

import json


def tool_call_name(tool_call, default=None) -> str:
    """Return the tool name from either call shape.

    Raises ValueError when the call has no name and no default is given.
    """
    function = getattr(tool_call, "function", None)
    if function is not None:
        name = getattr(function, "name", None)
        if name:
            return name

    name = getattr(tool_call, "name", None)
    if name:
        return name

    if default is not None:
        return default

    raise ValueError("Tool call does not contain a tool name.")


def tool_call_arguments(tool_call):
    """Return raw tool arguments (JSON string or dict) from either shape."""
    function = getattr(tool_call, "function", None)
    if function is not None and hasattr(function, "arguments"):
        return function.arguments

    if hasattr(tool_call, "arguments"):
        return tool_call.arguments

    raise ValueError("Tool call does not contain arguments")


def parse_tool_arguments(raw_arguments) -> dict:
    """Coerce raw arguments (JSON string or dict) into a dict."""
    if isinstance(raw_arguments, str):
        return json.loads(raw_arguments)
    if isinstance(raw_arguments, dict):
        return raw_arguments
    raise TypeError("Tool arguments must be a JSON string or dictionary")

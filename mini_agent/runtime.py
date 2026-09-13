import logging
import time

from .tool_calls import (
    parse_tool_arguments,
    tool_call_arguments,
    tool_call_name,
)
from .tool_result import ToolResult

logger = logging.getLogger(__name__)


class Runtime:

    def __init__(self, registry):
        self.registry = registry

    def execute(self, tool_call) -> ToolResult:

        start = time.perf_counter()

        try:
            # ---------------------------------
            # Normalize tool call
            # ---------------------------------
            
            name, arguments = self._parse_tool_call(
                tool_call
            )

            tool_call_id = tool_call.id

            # ---------------------------------
            # Get tool
            # ---------------------------------

            tool = self.registry.get(name)

            if tool is None:
                raise ValueError(
                    f"Unknown tool: {tool}"
                )

            # ---------------------------------
            # Validate arguments
            # ---------------------------------
            self._validate_arguments(
                tool,
                arguments,
            )


            # ---------------------------------
            # Execute
            # ---------------------------------

            result = tool.execute(arguments)

            duration = (time.perf_counter() - start)


            # ---------------------------------
            # Normalized result
            # ---------------------------------

            return ToolResult(
                tool_call_id=tool_call_id,
                name = name,
                arguments = arguments,
                content = str(result),
                success=True
            )


        except Exception as e:
                duration = (
                time.perf_counter() - start
                )

                # We may not have successfully parsed
                # the tool name, so determine it safely.
                name = tool_call_name(
                    tool_call,
                    default="<unknown>",
                )

                logger.warning(
                    "Tool %s failed after %.3fs: %s",
                    name,
                    duration,
                    e,
                )


                return ToolResult(
                    tool_call_id = getattr(
                        tool_call,
                        "id",
                        None,
                    ),
                    name = name,
                    arguments = arguments,
                    content = f"Tool error: {str(e)}",
                    success=False
                )



    # =====================================
    # Tool-call normalization
    # =====================================

    def _validate_arguments(self, tool, arguments):

        schema = tool.parameters

        required = schema.get(
            "required",
            []
        )

        properties = schema.get(
            "properties",
            {}
        )

        # Required fields
        for field in required:

            if field not in arguments:
                raise ValueError(
                    f"Missing required argument "
                    f"'{field}' for tool '{tool.name}'"
                )

        # Type checking
        for field, value in arguments.items():

            if field not in properties:
                raise ValueError(
                    f"Unexpected argument "
                    f"'{field}' for tool '{tool.name}'"
                )

            expected_type = properties[field].get(
                "type"
            )

            if expected_type == "string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"Argument '{field}' must be a string"
                    )

            elif expected_type == "number":
                if not isinstance(value, (int, float)):
                    raise ValueError(
                        f"Argument '{field}' must be a number"
                    )

            elif expected_type == "integer":
                if not isinstance(value, int):
                    raise ValueError(
                        f"Argument '{field}' must be an integer"
                    )

            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(
                        f"Argument '{field}' must be a boolean"
                    )

    def _parse_tool_call(self, tool_call):

        name = self._get_tool_name(tool_call)

        raw_arguments = self._get_tool_arguments(tool_call)

        arguments = parse_tool_arguments(raw_arguments)

        return name, arguments


    def _get_tool_name(self, tool_call):
        return tool_call_name(tool_call)


    def _get_tool_arguments(self, tool_call):
        return tool_call_arguments(tool_call)
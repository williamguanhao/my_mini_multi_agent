import json
import time

class Runtime:

    def __init__(self, registry, tracer=None):
        self.registry = registry
        self.tracer = tracer

    def execute(self, tool_call):

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
            # Trace start
            # ---------------------------------
            
            if self.tracer:
                self.tracer.log(
                    "TOOL_START",
                    {
                        "tool": name,
                        "tool_call_id": tool_call_id,
                        "arguments": arguments,
                    },
                )

            # ---------------------------------
            # Execute
            # ---------------------------------

            result = tool.execute(arguments)

            duration = (time.perf_counter() - start)

            # ---------------------------------
            # Trace end
            # ---------------------------------
            if self.tracer:
                self.tracer.log(
                    "TOOL_END",
                    {
                        "duration_ms": round(
                            duration * 1000,
                            2,
                        ),
                        "tool": name,
                        "success": True,
                        "content": str(result),
                    },
                )

            # ---------------------------------
            # Normalized result
            # ---------------------------------

            return {
                "success": True,
                "content": str(result),
                "tool_call_id": tool_call_id,
                "name": name,
                "arguments": arguments
            }

        except Exception as e:
                duration = (
                time.perf_counter() - start
                )

                # We may not have successfully parsed
                # the tool name, so determine it safely.
                name = self._get_tool_name(
                    tool_call
                )

                if self.tracer:
                    self.tracer.log(
                        "TOOL_END",
                        {
                            "duration_ms": round(
                                duration * 1000,
                                2,
                            ),
                            "tool": name,
                            "success": False,
                            "content": f"Tool error: {str(e)}",
                        },
                    )

                return {
                    "success": False,
                    "content": f"Tool error: {str(e)}",
                    "tool_call_id": getattr(
                        tool_call,
                        "id",
                        None,
                    ),
                    "name": name,
                    "arguments": {},
                }



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


        if isinstance(raw_arguments, str):
            arguments = json.loads(
                raw_arguments
            )
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            raise TypeError(
                "Tool arguments must be "
                "a JSON string or dictionary"
            )

        return name, arguments
        

    def _get_tool_name(self, tool_call):

        # OpenAI-style:
        #
        # tool_call.function.name
        #
        if hasattr(tool_call, "function"):
            return tool_call.function.name
                 # Custom ToolCall-style:

        # Custom ToolCall-style:
        #
        # tool_call.name
        #
        if hasattr(tool_call, "name"):
            return tool_call.name

        return "<unknown>"

    
    def _get_tool_arguments(self, tool_call):

        # OpenAI-style
        if hasattr(tool_call, "function"):
            return tool_call.function.arguments

        # Custom ToolCall-style
        if hasattr(tool_call, "arguments"):
            return tool_call.arguments

        raise ValueError(
            "Tool call does not contain arguments"
        )
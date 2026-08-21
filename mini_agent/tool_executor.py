from .runtime import Runtime
from .tool_result import ToolResult

class ToolExecutor:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime

    def execute(self, tool_call) -> ToolResult:
        return self.runtime.execute(tool_call)
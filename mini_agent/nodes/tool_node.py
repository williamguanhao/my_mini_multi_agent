"""ToolNode — executes the tool calls in the current decision."""

from graph.node import Node
from graph.state import GraphState

from ..tool_calls import tool_call_name
from .state_keys import DECISION, RUN_ID, TOOL_CALLS_LOG


class ToolNode(Node):

    def __init__(
            self,
            name: str,
            tool_executor,
            message_store=None,
            event_bus=None,
            event_factory=None,
    ):
        super().__init__(name)
        self.tool_executor = tool_executor
        self.message_store = message_store
        self.event_bus = event_bus
        self.event_factory = event_factory

    def execute(self, state: GraphState) -> GraphState:
        decision = state.get(DECISION) or {}
        if decision.get("type") != "tool":
            return state

        run_id = state.get(RUN_ID)
        log = list(state.get(TOOL_CALLS_LOG) or [])

        for tool_call in decision.get("calls") or []:
            tool_name = tool_call_name(tool_call)

            tool_started = None
            if self.event_factory is not None and run_id is not None:
                tool_started = self.event_factory.tool_started(
                    run_id, tool_name, state.step,
                )
                self._publish(tool_started)

            result = self.tool_executor.execute(tool_call)

            if self.event_factory is not None and run_id is not None:
                self._publish(
                    self.event_factory.tool_completed(
                        run_id,
                        result.name,
                        result.success,
                        state.step,
                        parent_event_id=(
                            tool_started.event_id if tool_started else None
                        ),
                    ),
                )

            if self.message_store is not None:
                self.message_store.add_tool(
                    tool_call_id=result.tool_call_id,
                    tool_name=result.name,
                    content=result.content,
                )

            log.append({
                "tool_call_id": result.tool_call_id,
                "name": result.name,
                "arguments": result.arguments,
                "content": result.content,
                "success": result.success,
            })

        state.set(TOOL_CALLS_LOG, log)
        return state

    def _publish(self, event):
        if self.event_bus is not None and event is not None:
            self.event_bus.publish(event)

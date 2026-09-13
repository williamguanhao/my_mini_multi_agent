"""AgentNode — the model-calling graph node.

One execution = one agent step: build context, call the model, persist
the assistant message, and write a `decision` into the graph state that
the router and downstream nodes consume.
"""

from graph.node import Node
from graph.state import GraphState

from .state_keys import DECISION, RUN_ID, USER_INPUT


class AgentNode(Node):

    def __init__(
            self,
            name: str,
            model_client,
            context_provider,
            registry,
            message_store=None,
            event_bus=None,
            event_factory=None,
    ):
        super().__init__(name)
        self.model_client = model_client
        self.context_provider = context_provider
        self.registry = registry
        self.message_store = message_store
        self.event_bus = event_bus
        self.event_factory = event_factory

    def execute(self, state: GraphState) -> GraphState:
        run_id = state.get(RUN_ID)
        self._publish(
            self._event("step_started", run_id, state.step),
        )

        context = self.context_provider.build(
            state.get(USER_INPUT, "")
        )

        self._publish(
            self._event("model_called", run_id, state.step),
        )
        response = self.model_client.generate(
            messages=context.messages,
            tools=self.registry.schemas(),
        )
        self._publish(
            self._event(
                "model_completed",
                run_id,
                state.step,
                len(response.tool_calls),
            ),
        )

        if self.message_store is not None:
            self.message_store.add_assistant(response)

        if response.tool_calls:
            decision = {"type": "tool", "calls": list(response.tool_calls)}
        else:
            decision = {"type": "answer", "content": response.content}

        state.set(DECISION, decision)
        return state

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _event(self, kind, run_id, step, tool_calls=None):
        """Build an event, or None when tracing is disabled."""
        if self.event_factory is None or run_id is None:
            return None
        if kind == "step_started":
            return self.event_factory.step_started(run_id, step)
        if kind == "model_called":
            return self.event_factory.model_called(run_id, step)
        return self.event_factory.model_completed(run_id, tool_calls, step)

    def _publish(self, event):
        if self.event_bus is not None and event is not None:
            self.event_bus.publish(event)

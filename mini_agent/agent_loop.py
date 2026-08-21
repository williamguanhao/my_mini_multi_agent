from .agent_state import AgentState
from .agent_result import AgentResult
from .context import ContextProvider
from .model import ModelClient
from .tool_executor import ToolExecutor
from .message_store import MessageStore
from .events import RunStarted
import uuid
class AgentLoop:

    def __init__(
            self,
            context_provider,
            model_client,
            tool_executor,
            registry,
            session,
            message_store,
            event_bus=None,
            event_factory=None,
            system_prompt=None,
            ):
        self.context_provider = context_provider
        self.model_client = model_client
        self.tool_executor = tool_executor

        self.registry = registry
        self.session = session
        self.message_store = message_store

        self.event_bus = event_bus
        self.event_factory = event_factory
        self.system_prompt = {
            "role": "system",
            "content": system_prompt
        }


    def run(
            self,
            user_input: str,
            max_steps: int = 10
        ) -> AgentResult:

        run_id = str(uuid.uuid4())

        state = AgentState(
            user_input=user_input
        )

        try:
            self.message_store.add_user(user_input)
            if self.event_bus:
                self.event_bus.publish(
                    self.event_factory.run_started(
                        run_id,
                        user_input,
                    )
                )

            for step in range(max_steps):
                state.step = step + 1
                self.event_factory.step_started(
                    run_id,
                    step+1,
                )
                # -------------------------
                # Context
                # -------------------------
                context = (
                    self.context_provider.build(
                        user_input
                    )
                )

                messages = [
                    self.system_prompt,
                    *context.messages,
                ]

                # -------------------------
                # Model
                # -------------------------

                self.event_bus.publish(
                    self.event_factory.model_called(
                        run_id
                    )
                )

                response = (
                    self.model_client.generate(
                        messages =messages,
                        tools = self.registry.schemas(),
                    )
                )

                self.event_bus.publish(
                    self.event_factory.model_completed(
                        run_id,
                        len(response.tool_calls),
                        )
                    )

                # -------------------------
                # Save model response
                # -------------------------

                self.message_store.add_assistant(
                    response
                )

                # -------------------------
                # Finished
                # -------------------------

                if not response.tool_calls:

                    self.event_bus.publish(
                        self.event_factory.run_completed(
                            run_id
                        )
                    )

                    return self._complete(
                        state,
                        response.content,
                    )
                
                # -------------------------
                # Tools
                # -------------------------

                for tool_call in response.tool_calls:

                    self.event_bus.publish(
                        self.event_factory.tool_started(
                            run_id,
                            tool_call.name,
                        )
                    )

                    result = (
                        self.tool_executor.execute(
                            tool_call
                        )
                    )

                    self.event_bus.publish(
                        self.event_factory.tool_completed(
                            run_id,
                            result.name,
                            result.success,
                        )
                    )

                    state.tool_calls.append(
                        {
                            "tool_call_id": (
                                result.tool_call_id
                            ),
                            "name": result.name,
                            "arguments": (
                                result.arguments
                            ),
                            "content": result.content,
                            "success": result.success,
                        }
                    )
                    self.message_store.add_tool(
                        tool_call_id = (
                            result.tool_call_id
                        ),
                        tool_name = result.name,
                        content = result.content,
                    )

            # --------------------------------
            # Maximum iteration reached
            # --------------------------------
            return AgentResult(
                output=None,
                status="max_steps",
                iterations=state.step,
                tool_calls=state.tool_calls,
                state=state,
            )
        
        except Exception as e:

            state.error = e

            self.event_bus.publish(
                self.event_factory.run_failed(
                    run_id,
                    e,
                )
            )

            return AgentResult(
                output=None,
                status="error",
                iterations=state.step,
                tool_calls=state.tool_calls,
                state=state,
                error=e,
            ) 

    # --------------------------------
    # A clean termination point
    # --------------------------------

    def _complete(
        self,
        state: AgentState,
        output: str | None,
    ) -> AgentResult:
        state.finished = True
        state.final_output = output

        return AgentResult(
            output=output,
            status="completed",
            iterations=state.step,
            tool_calls=state.tool_calls,
            state=state,
        )
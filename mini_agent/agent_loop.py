from .agent_state import AgentState
from .agent_result import AgentResult
from .tracer import RunTrace

import uuid
import time
import json
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
            trace_collector=None,
            ):
        self.context_provider = context_provider
        self.model_client = model_client
        self.tool_executor = tool_executor

        self.registry = registry
        self.session = session
        self.message_store = message_store

        self.event_bus = event_bus
        self.event_factory = event_factory
        self.trace_collector = trace_collector


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

                self._publish(
                    self.event_factory.run_start(
                        run_id,
                        user_input,                        
                    )
                )

            for step in range(max_steps):
                state.step = step + 1

                self._publish(
                    self.event_factory.step_started(
                        run_id,
                        state.step,
                    )
                )

                # -------------------------
                # Context
                # -------------------------
                context = (
                    self.context_provider.build(
                        user_input
                    )
                )

                messages = context.messages

                # -------------------------
                # Model
                # -------------------------

                self._publish(
                    self.event_factory.model_called(
                        run_id,
                        state.step,
                    )
                )

                response = (
                    self.model_client.generate(
                        messages =messages,
                        tools = self.registry.schemas(),
                    )
                )

                self._publish(
                    self.event_factory.model_completed(
                        run_id,
                        len(response.tool_calls),
                        state.step,
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

                    return self._complete(
                        state,
                        response.content,
                        run_id,
                    )
                
                # -------------------------
                # Execute tools
                # -------------------------

                for tool_call in response.tool_calls:

                    self._execute_tool(
                        tool_call=tool_call,
                        state=state,
                        run_id=run_id,
                        step=step,
                    ) 

            # --------------------------------
            # Maximum steps reached
            # --------------------------------
            return self._max_steps(
                state=state,
                run_id=run_id,
                max_steps=max_steps,
            )

        # --------------------------------
        # Tool exception
        # --------------------------------
        except Exception as error:

            self._fail(
                state=state,
                run_id=run_id,
                error=error
            )
        
    # =========================================================
    # Failure
    # =========================================================

    def _fail(
            self,
            state: AgentState,
            run_id: str,
            error: Exception,
    ) -> AgentResult:

        state.error = error,

        self._publish(
            self.event_factory.run_failed(
                run_id,
                error
            )
        )

        return AgentResult(
                output=None,
                status="error",
                iterations=state.step,
                tool_calls=state.tool_calls,
                state=state,
                error=error,
            ) 

    # =========================================================
    # Max steps
    # =========================================================

    def _max_steps(
        self,
        state: AgentState,
        run_id: str,
        max_steps: int,
    ) -> AgentResult:

        state.finished = True

        output = (
            f"Agent stopped after "
            f"{max_steps} steps."
        )

        state.final_output = output

        self._publish(
            self.event_factory.run_completed(
                run_id,
                output,
            )
        )

        return AgentResult(
            output=output,
            status="max_steps",
            iterations=state.step,
            tool_calls=state.tool_calls,
            state=state,
        )

    # =========================================================
    # Event publishing
    # =========================================================

    def _publish(self, event):

        if self.event_bus is None:
            return
        
        self.event_bus.publish(event)

    # --------------------------------
    # A clean termination point
    # --------------------------------

    def _complete(
        self,
        state: AgentState,
        output: str | None,
        run_id=None
    ) -> AgentResult:
        
        state.finished = True
        state.final_output = output

        if self.event_bus and run_id:
            self._publish(
                self.event_factory.run_completed(
                    run_id,
                    output,
                )
            )
        
        return AgentResult(
            output=output,
            status="completed",
            iterations=state.step,
            tool_calls=state.tool_calls,
            state=state,
        )
    
    # =========================================================
    # Tool execution
    # =========================================================

    def _execute_tool(
            self,
            tool_call,
            state: AgentState,
            run_id: str,
            step: int,
            ):

            tool_name = self._tool_name(tool_call)

            tool_started = (
                self.event_factory.tool_started(
                    run_id,
                    tool_name,
                    state.step,
                )
            )

            self._publish(
                tool_started
            )

            result = (
                self.tool_executor.execute(
                    tool_call
                )
            )



            state.tool_calls.append(
                {
                    "tool_call_id": result.tool_call_id,
                    "name": result.name,
                    "arguments": result.arguments,
                    "content": result.content,
                    "success": result.success,
                }
            )

            self._publish(
                self.event_factory.tool_completed(
                    run_id,
                    result.name,
                    result.success,
                    state.step,
                    tool_started.event_id
                )
            )


            self.message_store.add_tool(
                tool_call_id = result.tool_call_id,
                tool_name = result.name,
                content = result.content,
            )

    # =========================================================
    # Tool name normalization
    # =========================================================

    @staticmethod
    def _tool_name(tool_call) -> str:

        # OpenAI-style:
        #
        # tool_call.function.name
        #

        function = getattr(
            tool_call,
            "function",
            None,
        )

        if function is not None:

            name = getattr(
                function,
                "name",
                None,
            )

            if name:
                return name

        # Custom style:
        #
        # tool_call.name
        #

        name = getattr(
            tool_call,
            "name",
            None,
        )

        if name:
            return name

        raise ValueError(
            "Tool call does not contain "
            "a tool name."
        )
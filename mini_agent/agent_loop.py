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

        trace = RunTrace(
            run_id=run_id,
            input=user_input,
            started_at=time.time()
        )

        state = AgentState(
            user_input=user_input
        )

        try:

            self.message_store.add_user(user_input)

            if self.event_bus:

                self.event_bus.start_trace(
                    run_id,
                    user_input,
                )

                self.event_bus.publish(
                    self.event_factory.run_start(
                        run_id,
                        user_input,                        
                    )
                )

            for step in range(max_steps):
                state.step = step + 1

                self.event_bus.publish(
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

                messages = [
                    self.system_prompt,
                    *context.messages,
                ]

                # -------------------------
                # Model
                # -------------------------

                self.event_bus.publish(
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

                self.event_bus.publish(
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
                # Tools
                # -------------------------

                for tool_call in response.tool_calls:

                    tool_started = (
                        self.event_factory.tool_started(
                            run_id,
                            tool_call.name,
                            state.step,
                        )
                    )

                    self.event_bus.publish(
                        tool_started
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
                            state.step,
                            tool_started.event_id
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

        # --------------------------------
        # Tool exception
        # --------------------------------
        except Exception as e:

            state.error = e

            if self.event_bus:

                self.event_bus.publish(
                    self.event_factory.run_failed(
                        run_id,
                        e,
                    )
                )

                trace = self.event_bus.get_trace(run_id)

                if trace:
                    trace.fail(e)

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
        run_id=None
    ) -> AgentResult:
        
        state.finished = True
        state.final_output = output

        if self.event_bus and run_id:
            self.event_bus.publish(
                self.event_factory.run_completed(
                    run_id,
                    output,
                )
            )

            trace = self.event_bus.get_trace(run_id)
            
            if trace:
                trace.complete(output)

            for event in trace.events:
                print(
                    event.sequence,
                    event.event_type,
                    event.step,
                )

            print(
                json.dumps(
                    trace.to_dict(),
                    indent=2,
                    )
                )
        
        return AgentResult(
            output=output,
            status="completed",
            iterations=state.step,
            tool_calls=state.tool_calls,
            state=state,
        )
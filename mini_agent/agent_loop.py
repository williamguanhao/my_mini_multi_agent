from .agent_state import AgentState
from .agent_result import AgentResult
from .context import ContextProvider
from .model import ModelClient
from .tool_executor import ToolExecutor
from .message_store import MessageStore
class AgentLoop:

    def __init__(
            self,
            context_provider,
            model_client,
            tool_executor,
            registry,
            session,
            message_store,
            tracer=None,
            system_prompt=None,
            ):
        self.context_provider = context_provider
        self.model_client = model_client
        self.tool_executor = tool_executor

        self.registry = registry
        self.session = session
        self.message_store = message_store

        self.tracer = tracer
        self.system_prompt = {
            "role": "system",
            "content": system_prompt
        }


    def run(
            self,
            user_input: str,
            max_steps: int = 10
        ) -> AgentResult:

        state = AgentState(
            user_input=user_input
        )

        if self.tracer:
            run_id = self.tracer.start_run()

        try:
            self.message_store.add_user(user_input)
            if self.tracer:
                self.tracer.log(
                    "USER_MESSAGE",
                    {
                        "content": user_input
                    }
                )

            for step in range(max_steps):
                state.step = step + 1

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

                response = (
                    self.model_client.generate(
                        messages =messages,
                        tools = self.registry.schemas(),
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
                    )
                
                # -------------------------
                # Tools
                # -------------------------

                for tool_call in response.tool_calls:

                    result = (
                        self.tool_executor.execute(
                            tool_call
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

            self.tracer.log(
                "RUN_ERROR",
                {
                    "error": str(e)
                }
            )
            return AgentResult(
                output=None,
                status="error",
                iterations=state.step,
                tool_calls=state.tool_calls,
                state=state,
                error=e,
            ) 

        finally:
            if self.tracer:
                self.tracer.end_run()

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
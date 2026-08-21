from .agent_state import AgentState

class AgentLoop:

    def __init__(
            self,
            gateway,
            registry,
            session,
            runtime,
            retriever,
            tracer=None,
            system_prompt=None
            ):
        self.gateway = gateway
        self.registry = registry
        self.session = session
        self.runtime = runtime
        self.regtriver = retriever
        self.tracer = tracer
        self.system_prompt = {
            "role": "system",
            "content": system_prompt
        }


    def run(
            self,
            user_input: str,
            max_steps: int = 10
        ) -> str:

        state = AgentState(
            user_input=user_input
        )

        if self.tracer:
            run_id = self.tracer.start_run()

        try:
            self.session.add_user_message(user_input)
            if self.tracer:
                self.tracer.log(
                    "USER_MESSAGE",
                    {
                        "content": user_input
                    }
                )

            for step in range(max_steps):
                state.step = step + 1

                context = self.regtriver.retrieve(
                    self.session,
                    query = user_input
                )

                messages = [
                    self.system_prompt,
                    *context
                ]

                response = self.gateway.chat(
                    messages,
                    self.registry.schemas()
                )

                self.session.add_assistant_message(
                    response
                )

                if not response.tool_calls:
                    state.finished = True
                    state.final_output = response.content
                    return response.content

                for tool_call in response.tool_calls:
                    tool_response = self.runtime.execute(tool_call)

                self.session.add_tool_message(
                        tool_call_id=tool_response["tool_call_id"],
                        tool_name=tool_response["name"],
                        content=tool_response["content"],
                )

            raise RuntimeError(
                f"Agent exceeded maximum steps: {max_steps}"
            )
        except Exception as e:

            state.error = e

            self.tracer.log(
                "RUN_ERROR",
                {
                    "error": str(e)
                }
            )
            raise 

        finally:
            if self.tracer:
                self.tracer.end_run() 
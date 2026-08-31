from .agent_loop import AgentLoop

class Agent:

    def __init__(
            self,
            context_provider,
            model_client,
            tool_executor,
            registry,
            session,
            message_store,
            event_bus,
            event_factory,
    ):
        self.loop = AgentLoop(
            context_provider=context_provider,
            model_client=model_client,
            tool_executor=tool_executor,
            registry=registry,
            session=session,
            message_store=message_store,
            event_bus=event_bus,
            event_factory=event_factory,
        )

    def run(self, user_input:str, max_steps=10) -> str:
        result =  self.loop.run(
            user_input=user_input,
            max_steps=max_steps,
        )
        print(result)
        if result.status == "error":
            raise result.error


        if result.status == "max_steps":
            raise RuntimeError(
                f"Agent exceeded maximum steps: "
                f"{max_steps}"
            )

        return result.output or ""      




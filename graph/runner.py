from .executor import GraphExecutor
from .state import GraphState

class AgentGraphRunner:

    def __init__(
            self,
            agent_graph,
            executor=None,
            ):
        self.agent_graph = agent_graph
        self.exexutor = (
            executor
            or GraphExecutor
        )

    def run(
            self,
            input_text,
            run_id,
    ):
        state = GraphState()

        state.set(
            "input",
            input_text,
        )

        return self.exexutor.run(
            self.agent_graph.graph,
            state,
            run_id=run_id,
        )
from .graph import Graph
from .state import GraphState
from .exceptions import GraphExecutionLimit
from .state_diff import diff_states

class GraphExecutor:

    def __init__(
        self,
        event_bus=None,
        event_factory=None,
        max_steps: int = 100,
    ):
        self.event_bus = event_bus
        self.event_factory = event_factory
        self.max_steps = max_steps


    def run(
            self,
            graph,
            state: GraphState | None = None,
            run_id: str | None = None,
            max_steps: int =100
    ) -> GraphState:

        step_limit = (
            max_steps
            if max_steps is not None
            else self.max_steps
        )

        if state is None:
            state = GraphState()

        if run_id is None:
            raise ValueError(
                "run_id cannoot be empty"
            )

        current_node = Graph.START

        state.current_node = current_node

        for _ in range(max_steps):

            state_before = state.snapshot()
            # ---------------------------------------------
            # Find next node
            # ---------------------------------------------       
             
            edge = graph.get_next_edge(
                current_node,
                state,
            )

            next_node = edge.target

            # -----------------------------------------
            # Edge traversal event
            # -----------------------------------------

            self._edge_traversed(
                run_id=run_id,
                edge=edge,
                state=state,
            )

            # ---------------------------------------------
            # END
            # ---------------------------------------------

            if next_node == Graph.END:

                state.current_node = Graph.END
                state.finished = True

                return state   

            # ---------------------------------------------
            # Execute node
            # ---------------------------------------------
             
            node = graph.get_node(next_node)     


            state.current_node = next_node      

            state.step += 1
            self._node_started(
                run_id,
                node, 
                state,
            ) 

            try:
                state = node.execute(state)

            except Exception as error:

                state.error = error

                self._node_failed(
                    run_id,
                    node,
                    state,
                    error,
                )

                raise

            state_after = state.snapshot()

            state_diff = diff_states(state_before, state_after)

            self._node_completed(
                run_id,
                node,
                state,
                state_diff,
            )


            # ---------------------------------------------
            # Continue
            # ---------------------------------------------

            current_node = next_node

        raise GraphExecutionLimit(
            f"Graph exceeded max_steps={step_limit}"
        )

    def _publish(self, event):

        if (
            self.event_bus is not None
            and event is not None
        ):
            self.event_bus.publish(event)


    def _node_started(
            self,
            run_id,
            node,
            state,
    ):

        if self.event_factory is None:
            return

        event = ( 
                self.event_factory.node_started(
                run_id=run_id,
                node_name=node.name,
                state= state,
                state=state,
            )
        )

        self._publish(event)

    def _node_completed(
            self,
            run_id,
            node,
            state,
            state_diff,
    ):
        if self.event_factory is None:
            return

        event = (
            self.event_factory.node_completed(
                run_id=run_id,
                node_name=node.name,
                state=state,
                state_diff=state_diff,
            )
        )
        self._publish(event)

    def _edge_traversed(
        self,
        run_id,
        edge,
        state,
    ):

        if self.event_factory is None:
            return

        event = (
            self.event_factory.edge_traversed(
                run_id=run_id,
                source=edge.source,
                target=edge.target,
                step=state.step,
                route=edge.name,
            )
        )

        self._publish(event)
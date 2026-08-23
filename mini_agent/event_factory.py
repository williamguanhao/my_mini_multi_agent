import time
import uuid

from .events import Event


class EventFactory:

    def create(
            self,
            event_type: str,
            run_id: str,
            *,
            step: int | None = None,
            parent_event_id: str | None = None,
            payload:dict | None = None,
        ) -> Event:

        return Event(
            event_type=event_type,
            run_id=run_id,
            timestamp=time.time(),
            event_id=str(uuid.uuid4()),
            step=step,
            parent_event_id=parent_event_id,
            payload=payload or {},
        )

    def run_start(
            self,
            run_id,
            user_input,
        ):

        return self.create(
            "run_started",
            run_id,
            payload={
                "input": user_input
            },
        )

    def step_started(
            self,
            run_id,
            step,
        ):

        return self.create(
            "step_started",
            run_id,
            step=step,
        )

    def model_called(
        self,
        run_id,
        step=None,
    ):

        return self.create(
            "model_called",
            run_id,
            step=step,
        )

    def model_completed(
        self,
        run_id,
        tool_calls,
        step=None,
    ):
        return self.create(
            "model_completed",
            run_id,
            step=step,     
            payload={
                "tool_calls": tool_calls,
            },       
        )

    def tool_started(
        self,
        run_id,
        tool_name,
        step=None,
    ):

        return self.create(
            "tool_started",
            run_id,
            step=step,
            payload={
                "tool": tool_name,
            },
        )

    def tool_completed(
        self,
        run_id,
        tool_name,
        success,
        step=None,
        parent_event_id=None,
    ):

        return self.create(
            "tool_completed",
            run_id,
            step=step,
            parent_event_id=parent_event_id,
            payload={
                "tool": tool_name,
                "success": success,
            },
        )

    def run_completed(
        self,
        run_id,
        output=None,
    ):

        return self.create(
            "run_completed",
            run_id,
            payload={
                "output": output,
            },
        )

    def run_failed(
        self,
        run_id,
        error,
    ):

        return self.create(
            "run_failed",
            run_id,
            payload={
                "error": str(error),
            },
        )

    def node_started(
            self,
            run_id,
            node_name,
            state,
    ):
        return self.create(
            "node_started",
            run_id,
            step=state.step,
            payload={
                "node_name": node_name,
                "node_execution_id": f"{run_id}:{state.step}:{node_name}",
                "state": state,
            }
        )

    def node_completed(
            self,
            run_id,
            node_name,
            state,
            state_diff,
    ):
        return self.create(
            "node_completed",
            run_id,
            step=state.step,
            payload={
                "node_name": node_name,
                "node_execution_id": f"{run_id}:{state.step}:{node_name}",
                "state_diff": state_diff,
            }
        )

    def node_failed(
        self,
        run_id,
        node_name,
        step,
        error,
    ):

        return self.create(
            "run_failed",
            run_id,
            step=step,
            payload={
                "node_name": node_name,
                "error": str(error),
            },
        )

    def edge_traversed(
        self,
        run_id: str,
        source: str,
        target: str,
        step: int,
        condition=None,
    ):
        return self.create(
            event_type="edge_traversed",
            run_id=run_id,
            step=step,
            payload={
                "source": source,
                "target": target,
                "condition": condition,
            },
    )

    def route_selected(
        self,
        run_id: str,
        node_name: str,
        route: str,
        step: int,
    ):
        return self.create(
            event_type="route_selected",
            run_id=run_id,
            step=step,
            payload={
                "node": node_name,
                "route": route,
            },
        )
import time
import uuid

from .events import *


class EventFactory:

    def __init__(self):
        pass

    def run_started(
        self,
        run_id,
        user_input,
    ):

        return RunStarted(
            event_type="run_started",
            timestamp=time.time(),
            run_id=run_id,
            payload={
                "input": user_input,
            },
        )

    def step_started(
        self,
        run_id,
        step,
    ):

        return StepStarted(
            event_type="step_started",
            timestamp=time.time(),
            run_id=run_id,
            payload={
                "step": step,
            },
        )

    def model_called(
        self,
        run_id,
    ):

        return ModelCalled(
            event_type="model_called",
            timestamp=time.time(),
            run_id=run_id,
            payload={},
        )

    def model_completed(
        self,
        run_id,
        tool_calls,
    ):

        return ModelCompleted(
            event_type="model_completed",
            timestamp=time.time(),
            run_id=run_id,
            payload={
                "tool_calls": tool_calls,
            },
        )

    def tool_started(
        self,
        run_id,
        tool_name,
    ):

        return ToolStarted(
            event_type="tool_started",
            timestamp=time.time(),
            run_id=run_id,
            payload={
                "tool": tool_name,
            },
        )

    def tool_completed(
        self,
        run_id,
        tool_name,
        success,
    ):

        return ToolCompleted(
            event_type="tool_completed",
            timestamp=time.time(),
            run_id=run_id,
            payload={
                "tool": tool_name,
                "success": success,
            },
        )

    def run_completed(
        self,
        run_id,
    ):

        return RunCompleted(
            event_type="run_completed",
            timestamp=time.time(),
            run_id=run_id,
            payload={},
        )

    def run_failed(
        self,
        run_id,
        error,
    ):

        return RunFailed(
            event_type="run_failed",
            timestamp=time.time(),
            run_id=run_id,
            payload={
                "error": str(error),
            },
        )
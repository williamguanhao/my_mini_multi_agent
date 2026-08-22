from dataclasses import dataclass
from typing import Callable

from .tracer import RunTrace
from .events import Event
from .trace_validator import TraceValidator

@dataclass
class ReplayResult:
    run_id: str
    events_replayed: int
    status: str

class ReplayEngine:

    def __init__(self):
        self.handlers: dict[str, list[Callable]] = {}

        self.validator = TraceValidator()

    def subscribe(
        self,
        event_type: str,
        handler: Callable,
    ):
        self.handlers.setdefault(
            event_type,
            [],
        ).append(handler)

    def replay(
        self,
        trace: RunTrace,
    ) -> ReplayResult:

        self.validator.validate(trace)

        count = 0

        for event in sorted(
            trace.events,
            key=lambda event: event.sequence,
        ):

            self._dispatch(event)

            count += 1

        return ReplayResult(
            run_id=trace.run_id,
            events_replayed=count,
            status="completed",
        )

    def _dispatch(
        self,
        event: Event,
    ):

        handlers = self.handlers.get(
            event.event_type,
            [],
        )

        for handler in handlers:
            handler(event)
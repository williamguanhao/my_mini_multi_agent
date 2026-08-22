from dataclasses import dataclass, field
from typing import Any
import uuid
import time
from datetime import datetime
import json

@dataclass
class RunTrace:

    run_id: str

    input: str

    started_at: float

    ended_at: float | None = None

    status: str = "running"

    output: str | None = None

    events: list = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def add_event(self, event):

        event.sequence = len(
            self.events
        )

        self.events.append(event)

    def complete(
        self,
        output: str | None = None,
    ):

        self.status = "completed"

        self.output = output

        self.ended_at = time.time()

    def fail(
        self,
        error: Exception,
    ):

        self.status = "failed"

        self.ended_at = time.time()

        self.metadata[
            "error"
        ] = str(error)

    @property
    def duration(self):

        if self.ended_at is None:
            return None

        return (
            self.ended_at
            - self.started_at
        )

    def to_dict(self):

        return {
            "run_id": self.run_id,
            "input": self.input,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "output": self.output,
            "duration": self.duration,
            "metadata": self.metadata,
            "events": [
                event.to_dict()
                for event in self.events
            ],
        }

class Tracer:
    def __init__(self):
        self.run_id = None
        self.events = []

    def start_run(self):
        self.run_id = str(uuid.uuid4())

        self.log(
            "RUN_START",
            {}
        )
        return self.run_id

    def log(self, event, data):

        self.events.append({
            "event": event,
            "data": data,
        })

        print(
            f"[{event}]"
            f"{data}"
        )

    def end_run(self):
        self.log(
            "RUN_END",
            {}
        )

    def get_events(self):

        return self.events
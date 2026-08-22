from dataclasses import dataclass, field
from typing import Any
import time
import uuid



@dataclass
class Event:
    event_type: str
    run_id: str

    timestamp: float = field(
        default_factory=time.time
    )

    event_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    sequence: int = 0

    step: int | None = None

    parent_event_id: str | None = None

    payload: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "step": self.step,
            "parent_event_id": self.parent_event_id,
            "payload": self.payload,
        }

from dataclasses import dataclass
from typing import Any
import time
import uuid


@dataclass
class Event:
    event_type: str
    timestamp: float
    run_id: str
    payload: dict[str, Any]


@dataclass
class RunStarted(Event):
    pass


@dataclass
class StepStarted(Event):
    pass


@dataclass
class ModelCalled(Event):
    pass


@dataclass
class ModelCompleted(Event):
    pass


@dataclass
class ToolStarted(Event):
    pass


@dataclass
class ToolCompleted(Event):
    pass


@dataclass
class RunCompleted(Event):
    pass


@dataclass
class RunFailed(Event):
    pass
from abc import ABC, abstractmethod

from .tracer import RunTrace

class TraceStore(ABC):

    @abstractmethod
    def create(self, trace: RunTrace):
        pass

    @abstractmethod
    def save(self, trace: RunTrace):
        pass

    @abstractmethod
    def get(self, run_id: str) -> RunTrace | None:
        pass

    @abstractmethod
    def list_runs(self) -> list[RunTrace]:
        pass


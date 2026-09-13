from abc import ABC, abstractmethod


class Tool(ABC):

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def description(self):
        pass

    @property
    @abstractmethod
    def parameters(self):
        pass

    @abstractmethod
    def execute(self, argument):
        pass
from abc import ABC, abstractmethod

class EventHandler(ABC):

    @abstractmethod
    def handle(self, evnet):
         pass
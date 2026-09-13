import logging

logger = logging.getLogger(__name__)


class EventBus:

    def __init__(self):
        self.handlers = []

    def subscribe(self, handler):
        self.handlers.append(handler)

    def publish(self, event):

        for handler in self.handlers:

            try:
                handler.handle(event)

            except Exception as e:

                logger.warning(
                    "Event handler %s failed for %s: %s",
                    type(handler).__name__,
                    event.event_type,
                    e,
                )

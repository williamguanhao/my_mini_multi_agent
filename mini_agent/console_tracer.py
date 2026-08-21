from .event_handler import EventHandler

class ConsoleTracer(EventHandler):
    def handle(self, event):
        print(
            f"[{event.event_type}] "
            f"{event.payload}"
        )
from .event_handler import EventHandler

class TraceHandler(EventHandler):

    def handle(self, event):

        print(
            f"[{event.timestamp}] "
            f"{event.event_type}"
        )

        if event.payload:

            print(event.payload)
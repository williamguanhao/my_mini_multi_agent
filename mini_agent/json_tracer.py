import json


class JsonTracer:

    def __init__(self):
        self.events = []

    def handle(self, event):

        self.events.append(
            {
                "type": event.event_type,
                "timestamp": event.timestamp,
                "run_id": event.run_id,
                "payload": event.payload,
            }
        )

    def save(self, path):

        with open(path, "w") as f:
            json.dump(
                self.events,
                f,
                indent=2,
            )
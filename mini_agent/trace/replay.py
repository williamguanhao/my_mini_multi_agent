class TraceReplay:

    def __init__(self, events):

        self.events = events

    def steps(self):

        for event in self.events:

            yield event

    def trajectory(self):

        result = []

        for event in self.events:

            if event.event_type == "node_started":

                result.append(
                    {
                        "type": "node",
                        "node": event.payload[
                            "node"
                        ],
                        "step": event.step,
                    }
                )

            elif event.event_type == "edge_traversed":

                result.append(
                    {
                        "type": "edge",
                        "source":
                            event.payload["source"],
                        "target":
                            event.payload["target"],
                    }
                )

        return result
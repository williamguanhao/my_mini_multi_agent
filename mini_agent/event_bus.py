from .tracer import RunTrace

class EventBus:

    def __init__(self):
        self.handlers = []
        self.traces = {}

    def subscribe(self, handler):
        self.handlers.append(handler)

    def start_trace(
            self,
            run_id,
            user_input
    ):
        trace = RunTrace(
            run_id=run_id,
            input=user_input,
            started_at=__import__(
                "time"
            ).time(),
        )
        self.traces[run_id] = trace

        return trace

    def publish(self, event):

        trace = self.traces.get(
            event.run_id
        )

        if trace is not None:
            trace.add_event(event)

        for handler in self.handlers:

            try:
                handler.handle(event)

            except Exception as e:

                print(
                    f"Event handler failed: {e}"
                )

    def get_trace(
            self,
            run_id,
    ):
        return self.traces.get(
            run_id
        )
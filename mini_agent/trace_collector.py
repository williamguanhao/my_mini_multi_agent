from .tracer import RunTrace
import json

class TraceCollector:

    def __init__(self, store):
        self.store = store
        self.traces = {}

    def start(
        self,
        run_id,
        user_input,
        timestamp,
    ):
        trace = RunTrace(
            run_id=run_id,
            input=user_input,
            started_at=timestamp
        )

        self.traces[run_id] = trace

        self.store.create(trace)

        return trace

    def handle(self, event):

        if event.event_type == "run_started":
            trace = RunTrace(
                run_id=event.run_id,
                input = event.payload["input"],
                started_at=event.timestamp,
            )

            self.traces[
                event.run_id
            ] = trace

            self.store.create(trace)
        else:

            trace = self.traces.get(
                event.run_id
            )

            if trace is None:
                return
            
            trace.add_event(event)

            if event.event_type == "run_completed":

                trace.complete(
                    event.payload.get(
                        "output"
                    )
                )

                print(
                    json.dumps(
                        trace.to_dict(),
                        indent=2,
                        )
                )

                self.store.save(trace)

            elif event.event_type == "run_failed":

                trace.fail(
                    Exception(
                        event.payload.get(
                            "error"
                        )
                    )
                )

                self.store.save(trace)
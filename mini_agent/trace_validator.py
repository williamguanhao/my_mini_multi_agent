from .tracer import RunTrace

class TraceValidator:

    def validate(
        self,
        trace: RunTrace,
    ):

        if not trace.events:
            raise ValueError(
                "Trace contains no events."
            )

        sequences = [
            event.sequence
            for event in trace.events
        ]

        expected = list(
            range(len(sequences))
        )

        if sequences != expected:
            raise ValueError(
                "Trace event sequence "
                "is invalid."
            )

        for event in trace.events:

            if event.run_id != trace.run_id:
                raise ValueError(
                    "Event belongs to "
                    "another run."
                )

        return True
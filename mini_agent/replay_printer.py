class ReplayPrinter:

    def handle(self, event):

        indent = "  " * (
            (event.step or 1) - 1
        )

        print(
            f"{indent}"
            f"[{event.sequence}] "
            f"{event.event_type}"
        )

        if event.payload:

            print(
                f"{indent}"
                f"    {event.payload}"
            )
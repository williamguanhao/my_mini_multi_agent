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

                print(
                    f"Event handler failed: {e}"
                )
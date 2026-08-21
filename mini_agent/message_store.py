class MessageStore:

    def __init__(self, session):
        self.session = session

    def add_user(
            self,
            content: str
        ):
        self.session.add_user_message(
            content
        )

    def add_assistant(
            self,
            response,
        ):
        self.session.add_assistant_message(
            response
        )

    def add_tool(
            self,
            tool_call_id: str,
            tool_name: str,
            content: str,
        ):
        self.session.add_tool_message(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            content=content,
        )
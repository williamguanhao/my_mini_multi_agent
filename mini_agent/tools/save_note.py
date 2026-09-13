from ..tool import Tool


class SaveNoteTool(Tool):

    def __init__(self, memory, session_id):
        self.memory = memory
        self.session_id = session_id

    @property
    def name(self):
        return "save_note"

    @property
    def description(self):
        return (
            "Save an important piece of information "
            "to long-term memory."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "The information that should "
                        "be remembered."
                    ),
                }
            },
            "required": ["text"],
        }

    def execute(self, arguments):
        text = arguments["text"]

        self.memory.add_note(self.session_id, text)
        return "Note saved successfully."
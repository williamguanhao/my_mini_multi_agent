from ..tool import Tool


class ReadNotesTool(Tool):

    def __init__(self, memory, session_id):
        self.memory = memory
        self.session_id = session_id

    @property
    def name(self):
        return "read_notes"

    @property
    def description(self):
        return (
            "Read information stored in long-term memory. "
            "Use a keyword to find relevant notes, or "
            "leave the keyword empty to retrieve recent notes."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "Keyword to search for. "
                        "Use an empty string to retrieve recent notes."
                    ),
                }
            },
            "required": ["keyword"],
        }

    def execute(self, arguments):

        keyword = arguments["keyword"].strip()

        if keyword:
            notes = self.memory.search_notes(
                self.session_id,
                keyword
            )
        else:
            notes = self.memory.get_notes(
                self.session_id
            )

        if not notes:
            return "No relevant notes found."

    
        return "\n".join(
            f"- {note['content']}"
            for note in notes
        )
        

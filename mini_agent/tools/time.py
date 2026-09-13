from datetime import datetime

from ..tool import Tool


class GetTimeTool(Tool):

    @property
    def name(self):
        return "get_time"

    @property
    def description(self):
        return "Get the current local date and time."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, argument):

        now = datetime.now()
        return now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
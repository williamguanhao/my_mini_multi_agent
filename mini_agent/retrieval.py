import re


STOP_WORDS = {
    "what",
    "is",
    "the",
    "a",
    "an",
    "do",
    "i",
    "my",
    "you",
    "we",
    "are",
    "was",
    "were",
    "to",
    "of",
    "and",
    "in",
    "on",
    "for",
}


def keywords(text):
    words = re.findall(
        r"\b[a-zA-Z0-9_]+\b",
        text.lower(),
    )

    return [
        word
        for word in words
        if word not in STOP_WORDS
    ]

def clean_message(message):

    return {
        key: value
        for key, value in message.items()
        if key != "_id"
    }
class Retriever:

    def __init__(
            self, 
            memory,
            recent_limit=20,
            relevent_limit=10
    ):
        self.memory = memory
        self.recent_limit = recent_limit
        self.relevent_limit = relevent_limit

    def retrieve(self, 
                 session,
                 query,
    ):
        recent = self.memory.get_recent_messages(
            session_id = session.session_id,
            limit = self.recent_limit
        )

        relevant = []
        for keyword in keywords(query):
            matches = self.memory.search_messages(
                session_id = session.session_id,
                query=keyword,
                limit=self.relevent_limit
            )
            # Filter out tool results - they need their tool_calls to be valid
            # Also filter out assistant messages with tool_calls (will be in recent)
            relevant.extend([
                m for m in matches
                if m.get("role") in ("user", "assistant")
                and not m.get("tool_calls")
            ])
        return [
            clean_message(message)
            for message in self._validate_sequence(
                self._merge(recent, relevant)
            )
        ]

    def _validate_sequence(self, messages):
        """Drop messages that produce an invalid tool-call sequence.

        OpenAI-style APIs require every assistant message declaring
        `tool_calls` to be immediately followed by tool messages whose
        `tool_call_id` matches one of the declared ids. If a previous run
        crashed mid-execution, the DB may contain orphan rows that the API
        rejects with "tool call result does not follow tool call (2013)".

        This filter walks the merged list and drops:
          - assistant messages whose `tool_calls` are not all satisfied by
            the immediately-following tool messages
          - tool messages whose `tool_call_id` does not match any preceding
            assistant `tool_calls` declaration
        """
        result = []
        i = 0
        while i < len(messages):
            m = messages[i]
            if m.get("role") == "assistant" and m.get("tool_calls"):
                declared = {tc["id"] for tc in m["tool_calls"]}
                # Collect the run of tool messages that immediately follows.
                tool_msgs = []
                j = i + 1
                while j < len(messages) and messages[j].get("role") == "tool":
                    tool_msgs.append(messages[j])
                    j += 1
                matched = {
                    tm.get("tool_call_id")
                    for tm in tool_msgs
                    if tm.get("tool_call_id") in declared
                }
                if matched == declared:
                    result.append(m)
                    result.extend(tool_msgs)
                # else: orphan assistant(tool_calls) — skip it and its
                # associated tool messages (which would otherwise be
                # stray).
                i = j
                continue

            # Drop orphan tool messages with no preceding assistant tool_call.
            if m.get("role") == "tool":
                if (
                    not result
                    or result[-1].get("role") != "assistant"
                    or not result[-1].get("tool_calls")
                    or not any(
                        tc["id"] == m.get("tool_call_id")
                        for tc in result[-1]["tool_calls"]
                    )
                ):
                    i += 1
                    continue

            result.append(m)
            i += 1

        return result

    def _merge(self, recent, relevant):
        # Recent messages should take priority and maintain order
        # Relevant messages from search should only add context, not reorder
        messages = recent.copy()

        # Add relevant messages that are not already in recent
        recent_ids = {msg["_id"] for msg in recent}
        for msg in relevant:
            if msg["_id"] not in recent_ids:
                messages.append(msg)

        return messages
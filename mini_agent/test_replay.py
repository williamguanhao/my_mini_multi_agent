from mini_agent.sqlite_trace_store import SQLiteTraceStore
from mini_agent.replay import ReplayEngine


def test_replay_events():

    events = []

    replay = ReplayEngine()

    replay.subscribe(
        "tool_completed",
        lambda event: events.append(
            event
        ),
    )

    result = replay.replay(
        trace
    )
    print(result)
    assert (
        result.events_replayed
        == len(trace.events)
    )

    assert len(events) == 1

trace_store = SQLiteTraceStore("traces.db")

trace = trace_store.get(
    "d7d9764b-c267-4cf3-a024-7a6aad44d61a"
)
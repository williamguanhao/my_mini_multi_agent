import json
import sqlite3
from pathlib import Path

from .tracer import RunTrace
from .events import Event
from .trace_store import TraceStore

class SQLiteTraceStore(TraceStore):

    def __init__(self, path: str = "traces.db"):
        self.path = Path(path)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _initialize(self):

        with self._connect() as conn:

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    input TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    status TEXT NOT NULL,
                    output TEXT,
                    metadata TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    sequence INTEGER NOT NULL,
                    step INTEGER,
                    parent_event_id TEXT,
                    payload TEXT NOT NULL,

                    FOREIGN KEY(run_id)
                        REFERENCES runs(run_id)
                )
                """
            )

            conn.commit()

    def create(self, trace: RunTrace):

        with self._connect() as conn:

            conn.execute(
                """
                INSERT INTO runs (
                    run_id,
                    input,
                    started_at,
                    ended_at,
                    status,
                    output,
                    metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.run_id,
                    trace.input,
                    trace.started_at,
                    trace.ended_at,
                    trace.status,
                    trace.output,
                    json.dumps(
                        trace.metadata
                    ),
                ),
            )

            conn.commit()

    def save(self, trace: RunTrace):

        with self._connect() as conn:

            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id,
                    input,
                    started_at,
                    ended_at,
                    status,
                    output,
                    metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.run_id,
                    trace.input,
                    trace.started_at,
                    trace.ended_at,
                    trace.status,
                    trace.output,
                    json.dumps(
                        trace.metadata
                    ),
                ),
            )

            conn.execute(
                """
                DELETE FROM events
                WHERE run_id = ?
                """,
                (trace.run_id,),
            )

            for event in trace.events:

                conn.execute(
                    """
                    INSERT INTO events (
                        event_id,
                        run_id,
                        event_type,
                        timestamp,
                        sequence,
                        step,
                        parent_event_id,
                        payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.run_id,
                        event.event_type,
                        event.timestamp,
                        event.sequence,
                        event.step,
                        event.parent_event_id,
                        json.dumps(
                            event.payload
                        ),
                    ),
                )

            conn.commit()

    def get(
        self,
        run_id: str,
    ) -> RunTrace | None:

        with self._connect() as conn:

            run_row = conn.execute(
                """
                SELECT
                    run_id,
                    input,
                    started_at,
                    ended_at,
                    status,
                    output,
                    metadata
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

            if run_row is None:
                return None

            event_rows = conn.execute(
                """
                SELECT
                    event_id,
                    run_id,
                    event_type,
                    timestamp,
                    sequence,
                    step,
                    parent_event_id,
                    payload
                FROM events
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()

        trace = RunTrace(
            run_id=run_row[0],
            input=run_row[1],
            started_at=run_row[2],
            ended_at=run_row[3],
            status=run_row[4],
            output=run_row[5],
            metadata=json.loads(
                run_row[6] or "{}"
            ),
        )

        for row in event_rows:

            event = Event(
                event_id=row[0],
                run_id=row[1],
                event_type=row[2],
                timestamp=row[3],
                sequence=row[4],
                step=row[5],
                parent_event_id=row[6],
                payload=json.loads(
                    row[7]
                ),
            )

            trace.events.append(event)

        return trace

    def list_runs(self):

        with self._connect() as conn:

            rows = conn.execute(
                """
                SELECT
                    run_id,
                    input,
                    started_at,
                    ended_at,
                    status,
                    output,
                    metadata
                FROM runs
                ORDER BY started_at DESC
                """
            ).fetchall()

        traces = []

        for row in rows:

            traces.append(
                RunTrace(
                    run_id=row[0],
                    input=row[1],
                    started_at=row[2],
                    ended_at=row[3],
                    status=row[4],
                    output=row[5],
                    metadata=json.loads(
                        row[6] or "{}"
                    ),
                )
            )

        return traces
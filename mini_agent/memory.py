import json
import sqlite3


class SQLiteMemory:

    def __init__(self, db_path="memory.db"):
        self.db_path = db_path
        self._initialize_db()
    def _connect(self):
        return sqlite3.connect(self.db_path)
    def _initialize_db(self):
        with self._connect() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    tool_call_id TEXT,
                    tool_name TEXT,
                    tool_calls TEXT,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id)
                        REFERENCES sessions(id)
                )
            """)
    
    # --------------------------------------------------
    # Session
    # --------------------------------------------------

    def create_session(self, session_id):
        with self._connect() as conn:
            conn.execute("""
            INSERT OR IGNORE INTO sessions (id)
            VALUES (?)
            """,
            (session_id,),
            )

    # --------------------------------------------------
    # Write message
    # --------------------------------------------------

    def add_message(
            self,
            session_id,
            message
    ):
        tool_calls = message.get("tool_calls")
        if tool_calls:
            tool_calls = json.dumps(tool_calls)

        with self._connect() as conn:
            conn.execute("""
            INSERT INTO messages (
                session_id, 
                role, 
                content,
                tool_call_id,
                tool_name,
                tool_calls
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                message["role"],
                message["content"],
                message.get("tool_call_id"),
                message.get("name"),
                tool_calls
            )
        )


    # --------------------------------------------------
    # Helper function to turn SQLite rows to LLM messages
    # --------------------------------------------------

    def _rows_to_messages(self, rows):
        messages = []
        for message_id, role, content, tool_call_id, tool_name, tool_calls in rows:
            message = {
                "_id": message_id,
                "role": role,
                "content": content
            }
            if tool_call_id:
                message["tool_call_id"] = tool_call_id
            if tool_name:
                message["name"] = tool_name
            if tool_calls:
                message["tool_calls"] = json.loads(tool_calls)
            messages.append(message)
        return messages


    # --------------------------------------------------
    # Read recent messages
    # --------------------------------------------------

    def get_recent_messages(
            self, 
            session_id, 
            limit=20
        ):
        with self._connect() as conn:
            rows = conn.execute("""
            SELECT
                id, 
                role, 
                content,
                tool_call_id,
                tool_name,
                tool_calls
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
            ).fetchall()
        rows.reverse()  # Reverse to get chronological order
        return self._rows_to_messages(rows)

    # --------------------------------------------------
    # Search messages by keyword
    # --------------------------------------------------

    def search_messages(
            self,
            session_id,
            query,
            limit=10
    ):
        pattern = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute("""
            SELECT 
                id,
                role, 
                content,
                tool_call_id,
                tool_name,
                tool_calls
            FROM messages
            WHERE session_id = ? AND content LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, pattern, limit),
            ).fetchall()
        rows.reverse()  # Reverse to get chronological order
        return self._rows_to_messages(rows)

    def add_note(self, session_id, text):

        with self._connect() as conn:

            conn.execute("""
                        INSERT INTO notes (
                            session_id, 
                            content
                        )
                        VALUES (?, ?)
                        """,
                        (
                            session_id,
                            text
                        )
                    )

    def get_notes(self, session_id, limit=20):

        with self._connect() as conn:
            rows = conn.execute(
                    """
                    SELECT
                        id, 
                        content,
                        created_at
                    FROM notes
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (
                        session_id,
                        limit,
                    ),
                ).fetchall()

        return [
            {"_id": row[0],
             "content": row[1],
             "created_at": row[2],
            }
            for row in rows
        ]

    def search_notes(self, session_id, keyword, limit=20):

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    content,
                    created_at
                FROM notes
                WHERE session_id = ?
                  AND content LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    session_id,
                    f"%{keyword}%",
                    limit,
                ),
            ).fetchall()

        return [
            {"_id": row[0],
             "content": row[1],
             "created_at": row[2],
            }
            for row in rows
        ]


    
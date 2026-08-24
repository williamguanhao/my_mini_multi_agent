"""Tests for Retriever message-sequence validation.

Background: OpenAI-style chat APIs require that every assistant message
declaring `tool_calls` be immediately followed by `tool` messages whose
`tool_call_id` values match the declared ids. If a previous run crashed
mid-execution (e.g. an AttributeError before the tool ran), the DB may
contain orphan `assistant(tool_calls=[...])` rows that the API rejects.

Retriever must filter these out before handing messages to the LLM.
"""

import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GRAPH_DIR = ROOT / "graph"


def _ensure_graph_pkg():
    if "graph_pkg" not in sys.modules:
        pkg = types.ModuleType("graph_pkg")
        pkg.__path__ = [str(GRAPH_DIR)]
        sys.modules["graph_pkg"] = pkg


def _load(mod_name, file_name):
    _ensure_graph_pkg()
    full_name = f"graph_pkg.{mod_name}"
    spec = __import__(
        "importlib.util", fromlist=["spec_from_file_location"]
    ).spec_from_file_location(full_name, str(GRAPH_DIR / file_name))
    module = __import__(
        "importlib.util", fromlist=["module_from_spec"]
    ).module_from_spec(spec)
    sys.modules[full_name] = module
    setattr(sys.modules["graph_pkg"], mod_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def loaded_retrieval():
    """Load retrieval.py + its deps (memory + retriever) via importlib."""
    import importlib.util

    _ensure_graph_pkg()
    # memory and retrieval live in mini_agent/
    for mod_name, file_name in [
        ("memory", "memory.py"),
        ("retrieval", "retrieval.py"),
    ]:
        spec = importlib.util.spec_from_file_location(
            f"mini_agent.{mod_name}", str(ROOT / "mini_agent" / file_name)
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"mini_agent.{mod_name}"] = module
        spec.loader.exec_module(module)

    from mini_agent.memory import SQLiteMemory
    from mini_agent.retrieval import Retriever

    return {"SQLiteMemory": SQLiteMemory, "Retriever": Retriever}


@pytest.fixture
def temp_memory(loaded_retrieval):
    SQLiteMemory = loaded_retrieval["SQLiteMemory"]
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SQLiteMemory(db_path=str(Path(tmpdir) / "mem.db"))
        yield db


def _seed_messages(memory, session_id, messages):
    """Insert messages directly into the messages table."""
    import json
    import sqlite3
    with sqlite3.connect(memory.db_path) as conn:
        for m in messages:
            tc = m.get("tool_calls")
            tc_json = json.dumps(tc) if tc else None
            conn.execute(
                """
                INSERT INTO messages (
                    session_id, role, content,
                    tool_call_id, tool_name, tool_calls
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    m["role"],
                    m.get("content"),
                    m.get("tool_call_id"),
                    m.get("tool_name"),
                    tc_json,
                ),
            )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_valid_tool_sequence_kept(loaded_retrieval, temp_memory):
    """A complete assistant(tool_calls) → tool chain is preserved."""
    Retriever = loaded_retrieval["Retriever"]
    session_id = "s1"
    _seed_messages(temp_memory, session_id, [
        {"role": "user", "content": "what is 2+2?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_abc",
                "function": {"name": "calculator", "arguments": "{}"},
            }],
        },
        {
            "role": "tool",
            "tool_call_id": "call_abc",
            "tool_name": "calculator",
            "content": "4",
        },
        {"role": "assistant", "content": "It's 4."},
    ])

    r = Retriever(temp_memory, recent_limit=20, relevent_limit=10)
    msgs = r.retrieve(types.SimpleNamespace(session_id=session_id), "2+2")

    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "tool", "assistant"]


def test_orphan_assistant_tool_calls_dropped(loaded_retrieval, temp_memory):
    """Assistant(tool_calls=[X]) without a following tool(X) is dropped."""
    Retriever = loaded_retrieval["Retriever"]
    session_id = "s2"
    _seed_messages(temp_memory, session_id, [
        {"role": "user", "content": "what is 2+2?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "call_orphan",
                "function": {"name": "calculator", "arguments": "{}"},
            }],
        },
        # ← gap: no tool(call_orphan) here
        {"role": "user", "content": "get time"},
    ])

    r = Retriever(temp_memory, recent_limit=20, relevent_limit=10)
    msgs = r.retrieve(types.SimpleNamespace(session_id=session_id), "time")

    # The orphan assistant(tool_calls) must be filtered out
    for m in msgs:
        if m["role"] == "assistant":
            assert not m.get("tool_calls"), \
                f"orphan assistant(tool_calls) leaked: {m}"
    # Both user messages should still be there
    assert sum(1 for m in msgs if m["role"] == "user") == 2


def test_orphan_tool_message_dropped(loaded_retrieval, temp_memory):
    """A tool message without a preceding assistant(tool_calls) is dropped."""
    Retriever = loaded_retrieval["Retriever"]
    session_id = "s3"
    _seed_messages(temp_memory, session_id, [
        {"role": "user", "content": "hello"},
        {
            "role": "tool",
            "tool_call_id": "call_stray",
            "tool_name": "calculator",
            "content": "99",
        },
        {"role": "user", "content": "are you there?"},
    ])

    r = Retriever(temp_memory, recent_limit=20, relevent_limit=10)
    msgs = r.retrieve(types.SimpleNamespace(session_id=session_id), "hello")

    assert all(m["role"] != "tool" for m in msgs), \
        f"orphan tool message leaked: {msgs}"


def test_partial_tool_match_drops_assistant(loaded_retrieval, temp_memory):
    """If only some of an assistant's tool_calls have matching tool results,
    the assistant message must still be dropped (the API needs the full chain)."""
    Retriever = loaded_retrieval["Retriever"]
    session_id = "s4"
    _seed_messages(temp_memory, session_id, [
        {"role": "user", "content": "two things"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call_a", "function": {"name": "t1", "arguments": "{}"}},
                {"id": "call_b", "function": {"name": "t2", "arguments": "{}"}},
            ],
        },
        # Only call_a has a tool result; call_b is missing
        {
            "role": "tool",
            "tool_call_id": "call_a",
            "tool_name": "t1",
            "content": "result-a",
        },
        {"role": "user", "content": "next question"},
    ])

    r = Retriever(temp_memory, recent_limit=20, relevent_limit=10)
    msgs = r.retrieve(types.SimpleNamespace(session_id=session_id), "things")

    # The incomplete-chain assistant must be dropped (API would reject).
    for m in msgs:
        if m["role"] == "assistant":
            assert not m.get("tool_calls"), \
                f"partially-satisfied assistant(tool_calls) leaked: {m}"
    # The orphan tool(call_a) — whose parent assistant was dropped — must
    # also be dropped, otherwise it would be a stray tool message.
    assert all(m["role"] != "tool" for m in msgs)
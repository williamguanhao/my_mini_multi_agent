# MCP Servers in mini_agent

This directory holds standalone Model Context Protocol (MCP) servers that
expose finance and web-search tools to `mini_agent`. The agent connects to
them as subprocesses at startup; each server speaks JSON-RPC over stdio.

## Table of Contents

1. [What is MCP](#1-what-is-mcp)
2. [How MCP works: server and client](#2-how-mcp-works-server-and-client)
3. [Available MCP servers](#3-available-mcp-servers)
4. [What MCP takes in and emits: the full flow](#4-what-mcp-takes-in-and-emits-the-full-flow)
5. [When does the server start? Lifecycle](#5-when-does-the-server-start-lifecycle)
6. [Built-in tools vs MCP tools](#6-built-in-tools-vs-mcp-tools)
7. [Technical difficulties and how they were solved](#7-technical-difficulties-and-how-they-were-solved)
8. [Adding a new MCP server](#8-adding-a-new-mcp-server)

---

## 1. What is MCP

**Model Context Protocol (MCP)** is Anthropic's standard for connecting
AI agents to external tools. It's a **client-server JSON-RPC** protocol with
three primitive types:

| Primitive | Who provides | Purpose |
|---|---|---|
| **Tools** | The server | Functions the agent can call (the only one we use) |
| **Resources** | The server | Named data blobs the agent can read — **out of scope** for us |
| **Prompts** | The server | Pre-written prompt templates — **out of scope** for us |

A **client** (our agent) connects to a **server** (a finance tool provider),
discovers what tools it offers, and calls them via JSON-RPC.

The transport is **stdio**: the client spawns the server as a subprocess and
exchanges JSON-RPC messages line-by-line on stdin/stdout.

## 2. How MCP works: server and client

### Server

A server is a **standalone Python process** that registers tool handlers.
Here's the minimum (real example in `mcp_servers/websearch/server.py`):

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools import web_search       # pure-Python, no MCP

server = Server("websearch")

_TOOL_DEFS = [Tool(
    name="web_search",
    description="Run a web search via the ddgs metasearch package.",
    inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
)]
_TOOL_HANDLERS = {"web_search": web_search}

@server.list_tools()
async def list_tools():
    return _TOOL_DEFS

@server.call_tool()
async def call_tool(name, arguments):
    return [TextContent(type="text", text=_TOOL_HANDLERS[name](**arguments))]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

asyncio.run(main())
```

The `@server.list_tools()` and `@server.call_tool()` decorators wire the
SDK's JSON-RPC handlers to your functions. The SDK does all the framing.

### Client

`mini_agent` connects via `mini_agent/mcp.py`. There are three classes:

```
mini_agent/mcp.py
├── BackgroundLoop    persistent event loop on a daemon thread
├── MCPClient         owns a BackgroundLoop + an MCP subprocess
└── MCPToolAdapter    bridges sync Tool.execute → MCPClient.call_tool
```

**`BackgroundLoop`** — runs `asyncio.new_event_loop()` on a daemon thread
forever. Provides `run(coro)` which submits a coroutine via
`asyncio.run_coroutine_threadsafe` and blocks until done. All MCP async
work for one client uses this loop, so stdio streams and anyio cancel
scopes stay coherent.

**`MCPClient`** — sync public API:

```python
client = MCPClient(command="python", args=["-m", "server"], cwd="mcp_servers/yfinance")
client.connect()             # spawn subprocess, init MCP session
tools = client.list_tools()  # returns list[MCPToolAdapter]
result = client.call_tool("get_stock_price", {"ticker": "AAPL"})  # sync!
client.disconnect()          # kill subprocess, stop background loop
```

**`MCPToolAdapter`** — inherits from mini_agent's `Tool` base class. Stores
a reference to the parent `MCPClient`. `execute(arguments)` is sync and
just calls `client.call_tool(name, arguments)`.

## 3. Available MCP servers

| Server | Tools | API key? | Notes |
|---|---|---|---|
| `mcp_servers/yfinance` | `get_stock_price`, `get_history`, `get_fundamentals` | No | Stock data |
| `mcp_servers/fred` | `get_series`, `search_series` | Yes (`FRED_API_KEY` in `.env`) | Macro time series |
| `mcp_servers/websearch` | `web_search` | No | ddgs metasearch (DuckDuckGo + fallback engines) |

All three are wired into `mini_agent/main.py:setup_mcp_clients()` and start
automatically when the agent boots.

### Layout of each server

```
mcp_servers/<name>/
├── pyproject.toml     installable as its own package
├── __init__.py        (empty, marks the directory)
├── server.py          MCP entry point — thin wrapper
└── tools.py           pure-Python tool functions (testable without MCP)
```

**The key separation:** all logic lives in `tools.py` (pure Python, mockable
in tests). `server.py` is a thin MCP wrapper that registers handlers
dispatching to `tools.py` functions. This means `tests/test_mcp_servers.py`
imports `mcp_servers/yfinance.tools` directly and patches yfinance — no
MCP machinery needed in tests.

## 4. What MCP takes in and emits: the full flow

Here's what happens when you ask "what is AAPL stock price?":

```
User → "what is AAPL stock price?"
   ↓
[1] mini_agent CLI starts
   ↓
[2] main.py:setup_mcp_clients(registry) (sync)
   │
   ├─ Creates 3 MCPClient instances (yfinance, fred, websearch)
   ├─ For each:
   │     - client.connect()
   │       ├─ spawns subprocess: python -m server in mcp_servers/yfinance/
   │       ├─ opens stdio pipes
   │       └─ sends JSON-RPC initialize → server replies with capabilities
   │     - client.list_tools()
   │       └─ sends JSON-RPC tools/list → server replies with [Tool, Tool, Tool]
   │     - registry.register(tool) for each returned adapter
   ↓
[3] Chat loop runs (sync)
   ↓
[4] model_client.generate(messages, tools=registry.schemas())
   │
   │ LLM sees tools=[get_stock_price, get_history, get_fundamentals, ...]
   │ LLM returns a tool call: name="get_stock_price", arguments={"ticker": "AAPL"}
   ↓
[5] tool_executor.execute(tool_call)
   │
   │ Runtime.execute() looks up tool by name → finds MCPToolAdapter
   ↓
[6] MCPToolAdapter.execute({"ticker": "AAPL"})
   │
   │ client.call_tool("get_stock_price", {"ticker": "AAPL"})
   │   └─ self._loop.run(self._call_tool_async(...))
   │      └─ BackgroundLoop thread does:
   │         - sends JSON-RPC tools/call → subprocess
   │         - subprocess runs web_search or yfinance.Ticker(...).info
   │         - returns string result
   ↓
[7] ToolResult returned to agent, formatted, shown to LLM
   ↓
[8] LLM produces final answer: "Apple Inc. (AAPL) is currently trading at $317.30."
```

### What the LLM sees

The LLM has no idea whether a tool is built-in or MCP. It sees the same
JSON schema, calls the same `function.name`, gets a string result. The
distinction only matters for tool loading.

### What goes over stdio (JSON-RPC example)

```jsonc
// Client → Server: "what tools do you have?"
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

// Server → Client: "here are my tools"
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "tools": [{
      "name": "get_stock_price",
      "description": "Get the current market price for a ticker symbol.",
      "inputSchema": {
        "type": "object",
        "properties": {"ticker": {"type": "string"}},
        "required": ["ticker"]
      }
    }]
  }
}

// Client → Server: "call get_stock_price with AAPL"
{
  "jsonrpc": "2.0", "id": 2,
  "method": "tools/call",
  "params": {"name": "get_stock_price", "arguments": {"ticker": "AAPL"}}
}

// Server → Client: "Apple Inc. (AAPL): $317.30"
{
  "jsonrpc": "2.0", "id": 2,
  "result": {
    "content": [{"type": "text", "text": "Apple Inc. (AAPL): $317.30"}],
    "isError": false
  }
}
```

## 5. When does the server start? Lifecycle

Servers are spawned **when mini_agent starts** and killed **when it exits**.

```
main.py runs
   │
   ├─ build built-in tools (GetTimeTool, CalculatorTool, etc.)
   ├─ build ToolRegistry(tools)
   ├─ setup_mcp_clients(registry)              ← MCP servers spawn here
   │     │
   │     ├─ yfinance subprocess starts
   │     ├─ fred subprocess starts
   │     ├─ websearch subprocess starts
   │     └─ register discovered tools in registry
   │
   ├─ build Runtime, agent, etc.
   ├─ chat loop (sync, blocks on input())
   │
   └─ [user types "quit" or Ctrl-C]
         │
         └─ teardown_mcp_clients(mcp_clients)  ← subprocesses killed here
```

Each server is a real OS process. You can see them in `ps` while mini_agent
is running:

```bash
$ ps -ef | grep "mcp_servers"
python -m server    ← yfinance subprocess
python -m server    ← fred subprocess
python -m server    ← websearch subprocess
```

If a server crashes mid-session, the agent continues without that server's
tools (the `try/except` in `setup_mcp_clients` swallows startup errors).

## 6. Built-in tools vs MCP tools

| Aspect | Built-in tool (`mini_agent/tools/`) | MCP tool |
|---|---|---|
| **Process** | Same Python process as agent | Separate OS subprocess |
| **Language** | Python only | Any language (we use Python) |
| **State** | None across calls | Can hold connections (e.g., DB sessions) |
| **Deployment** | `pip install mini_agent` includes them | Standalone package; shareable with other agents |
| **Sharing** | mini_agent-specific | Standard protocol; works with Claude Desktop, Cursor, etc. |
| **Discovery** | Hardcoded in `main.py` | Runtime `tools/list` JSON-RPC call |
| **Failure isolation** | Crash = agent crash | Crash = one failed call, agent survives |
| **Setup cost** | One Python file | Package + entrypoint + subprocess spawn |
| **Latency per call** | ~microseconds | ~milliseconds (subprocess + JSON parse) |

### When to use which

**Built-in tools** when:
- Tool is simple and stateless
- Only your agent uses it
- Latency matters
- You want zero deployment complexity

**MCP tools** when:
- You want to share with other agents
- Tool needs persistent state
- Different teams own different tools
- You want language flexibility
- You want failure isolation

### How the agent sees them

The LLM **cannot tell** whether a tool is built-in or MCP. Both appear in the
`tools=` parameter the same way. The `ToolRegistry.schemas()` returns the
same JSON shape for both. `Runtime.execute(tool_call)` looks up by name and
calls `execute(arguments)` — whether the tool came from `mini_agent/tools/`
or from a subprocess.

### The adapter: `MCPToolAdapter`

The key bridge is `MCPToolAdapter`:

```python
class MCPToolAdapter(Tool):
    """Adapts an MCP-discovered tool to mini_agent's sync Tool interface."""
    def __init__(self, client, name, description, parameters):
        self._client = client
        self._name = name
        self._description = description
        self._parameters = parameters

    @property
    def name(self): return self._name
    @property
    def description(self): return self._description
    @property
    def parameters(self): return self._parameters

    def execute(self, arguments):
        return self._client.call_tool(self._name, arguments)
```

It **inherits from `Tool`**, so it satisfies the existing `ToolRegistry`,
`Runtime`, `AgentLoop`, and `GraphAgent` contracts without any changes.
Adding more MCP servers requires zero changes to those.

## 7. Technical difficulties and how they were solved

### D1: MCP 2.x vs 1.x API

**Problem:** The plan was written for MCP 1.x. `uv lock` resolved to
`mcp==2.1.1`, which had major API changes (`FastMCP` renamed to `MCPServer`,
old `@server.list_tools()` decorator pattern removed).

**Fix:** Pinned `mcp[cli]>=1.0,<2` in `pyproject.toml`. Reverted
`mcp_servers/yfinance/server.py` to the 1.x pattern. Lesson: **when the
plan specifies an SDK version, pin to it explicitly** — `uv` may resolve
to a newer major version with breaking changes.

### D2: `asyncio.run()` cross-loop cancel scope errors

**Problem:** First cut of `main.py` had three separate `asyncio.run()`
calls (one for `setup_mcp_clients`, one for `client.list_tools()`, one for
teardown). Each created a new event loop. `anyio`'s cancel scopes (which
back MCP's stdio_client) can't cross event loop boundaries — leading to:

```
RuntimeError: Attempted to exit cancel scope in a different task
             than it was entered in
```

**Fix:** Collapsed all async work into one `asyncio.run(setup_mcp_clients(registry))`
that does connect + list_tools + register in a single event loop.

### D3: `MCPToolAdapter.execute()` calling `asyncio.run()` per tool call

**Problem:** Even with one setup loop, each tool call inside the chat loop
was `asyncio.run(coro)` — creating a new loop and crossing boundaries
again. The tool would fail with `Tool error: ` (empty message).

**Fix:** Replaced with a **persistent background loop pattern**:

```
BackgroundLoop (daemon thread, loop.run_forever)
   │
   ├─ self.run(coro) submits via asyncio.run_coroutine_threadsafe
   └─ blocks on the future until result is ready
```

`MCPToolAdapter.execute()` is pure sync. `MCPClient` owns a `BackgroundLoop`
and all its methods (`connect`, `list_tools`, `call_tool`, `disconnect`)
are sync. Lesson: **for anyio + stdio transports, use one persistent
loop, never `asyncio.run()`**.

### D4: `python` not in subprocess PATH

**Problem:** `subprocess.Popen(["python", ...])` failed with
`FileNotFoundError: No such file or directory: 'python'` because
`uv run` didn't put `python` on the subprocess's PATH.

**Fix:** Use `sys.executable` in `main.py:setup_mcp_clients()`. This is the
path to the running interpreter, guaranteed to work.

### D5: `cwd` required for flat-layout modules

**Problem:** `mcp_servers/yfinance/server.py` does `from tools import ...`
(flat layout, not a package). When spawned without `cwd=`, the subprocess
can't find `tools.py`.

**Fix:** `MCPClient(command, args, cwd="mcp_servers/yfinance")`. The cwd
must be the directory containing `tools.py`.

### D6: Test mocking across import boundaries

**Problem:** Tests for FRED tried `patch("fredapi.Fred")` but `tools.py`
had `from fredapi import Fred` at module load, so the test patched the
wrong reference.

**Fix:** `patch.object(fred_tools, "Fred")` patches the bound name in the
`tools.py` module's namespace.

### D7: FRED API key — env var vs imported config

**Problem:** Tests for FRED originally mocked `os.environ` to test the
"missing key" case. But `tools.py` was changed to
`from mini_agent.config import FRED_API_KEY`, binding the value at import
time. `os.environ` patches no longer worked.

**Fix:** `patch.object(fred_tools, "FRED_API_KEY", None)` patches the bound
name directly. Same pattern as D6.

## 8. Adding a new MCP server

Say you want to add `mcp_servers/sec_filings/` for SEC EDGAR filings.

1. **Scaffold the package:**
```bash
mkdir -p mcp_servers/sec_filings
```

`mcp_servers/sec_filings/pyproject.toml`:
```toml
[project]
name = "mcp-sec-filings"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["mcp[cli]<2", "edgartools>=1.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = ["server", "tools"]
```

`mcp_servers/sec_filings/__init__.py`: empty file.

2. **Write `tools.py`** (pure Python, mockable):
```python
def get_10k_filing(ticker: str, year: int = 2024) -> str:
    """Fetch the most recent 10-K filing for `ticker`."""
    # ... edgartools calls ...
    return f"{ticker} 10-K ({year}): ..."
```

3. **Write `server.py`** (thin MCP wrapper):
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from tools import get_10k_filing

server = Server("sec_filings")
_TOOL_DEFS = [Tool(name="get_10k_filing", description=..., inputSchema=...)]
_TOOL_HANDLERS = {"get_10k_filing": get_10k_filing}

@server.list_tools()
async def list_tools(): return _TOOL_DEFS

@server.call_tool()
async def call_tool(name, arguments):
    return [TextContent(type="text", text=_TOOL_HANDLERS[name](**arguments))]

async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    import asyncio; asyncio.run(main())
```

4. **Add tests to `tests/test_mcp_servers.py`** — patch `edgartools`,
assert format.

5. **Install and wire into `main.py`:**
```bash
uv pip install -e mcp_servers/sec_filings
```

In `main.py:setup_mcp_clients()`, add:
```python
MCPClient(command=sys.executable, args=["-m", "server"], cwd="mcp_servers/sec_filings"),
```

6. **Verify** by running `uv run mini-agent --engine graph` and asking the
agent to fetch a 10-K.

That's it. The new server's tools appear in the LLM's `tools=` parameter
alongside everything else, no other code changes needed.

---

## Things worth knowing

- **All MCP work is async on the client side.** The `MCPToolAdapter` makes
  it look sync to mini_agent, but internally every call goes through
  `BackgroundLoop.run(coro)`. If you see weird "loop closed" errors, check
  that you're not bypassing the BackgroundLoop with raw `asyncio.run()`.

- **stdio transports don't survive process death.** When the parent Python
  process exits, MCP subprocesses die automatically. Don't try to keep
  them alive across `main()` boundaries.

- **The `cwd` parameter is required.** Without it, the server subprocess
  can't find `tools.py` (since the layout is flat, not a package).

- **APIs that need keys must be configured before subprocess spawn.** The
  FRED server reads `FRED_API_KEY` from `mini_agent.config` at module
  import. If you change the key, restart the agent.

- **The protocol is JSON-RPC over stdin/stdout.** Debugging tip:
  `echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | python -m server`
  to see what your server replies.

- **Add new tools to a server by editing `server.py`'s `_TOOL_DEFS` and
  `_TOOL_HANDLERS` dicts.** Adding a tool doesn't require restarting
  mini_agent's class hierarchy; the registry picks it up on next startup.

- **`/tmp/mcp_hello/server.py`** (from Phase 1, Task 2) is the minimum
  viable MCP server — one `echo` tool, stdio transport. Useful as a
  template when starting from scratch.
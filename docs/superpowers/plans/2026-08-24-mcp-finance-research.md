# MCP Finance Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **For the learner (you):** This plan doubles as a learning path. Every phase starts with "**What you'll learn**", has a "**What just happened**" recap at the end, and produces a working artifact. If you stop after any phase, you have something runnable.

**Goal:** Make `mini_agent` an MCP client that connects to standalone finance MCP servers (yfinance for stocks, FRED for macro), so the agent can answer real-world finance questions.

**Architecture:** Each MCP server is its own installable Python package in `mcp_servers/`. Servers expose tools via the official `mcp` Python SDK over stdio transport. A new `mini_agent.mcp.MCPClient` class spawns server subprocesses, discovers tools, and adapts them into `mini_agent.tool.Tool` instances that plug into the existing `ToolRegistry` unchanged.

**Tech Stack:** Python 3.11+, official `mcp` package, `yfinance` (already in `pyproject.toml`), `fredapi`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-08-24-mcp-finance-research-design.md`

## Global Constraints

- Use the **official `mcp` Python SDK** (do not reimplement the protocol).
- **stdio transport only** in v1 (no HTTP/SSE).
- **MCP tools only** (no resources, no prompts).
- Each MCP server is its **own installable Python package** under `mcp_servers/`.
- Servers are **pure-Python** subprocesses the client spawns at runtime — no Docker, no cloud.
- **YAGNI:** no auth beyond env-var API keys; no production deployment; no Web UI.
- Test the tool logic without MCP (mock the SDK); test MCP client with an in-process fake server; manual smoke test for the full round-trip.
- All work left **uncommitted in the working tree** — user commits.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `mcp_servers/README.md` | **Create (Phase 1)** | What the directory is for, how to add a server |
| `mcp_servers/yfinance/pyproject.toml` | **Create (Phase 2)** | Package metadata for yfinance server |
| `mcp_servers/yfinance/server.py` | **Create (Phase 2→3)** | MCP server entrypoint, registers tool handlers |
| `mcp_servers/yfinance/tools.py` | **Create (Phase 2→3)** | Pure-Python tool functions (testable without MCP) |
| `mcp_servers/fred/pyproject.toml` | **Create (Phase 5)** | Package metadata for FRED server |
| `mcp_servers/fred/server.py` | **Create (Phase 5)** | MCP server entrypoint |
| `mcp_servers/fred/tools.py` | **Create (Phase 5)** | Pure-Python tool functions |
| `mini_agent/mcp.py` | **Create (Phase 4)** | `MCPClient` class + `Tool` adapter |
| `mini_agent/main.py` | **Modify (Phase 4)** | Add MCP setup/teardown, register MCP tools in `ToolRegistry` |
| `tests/test_mcp_servers.py` | **Create (Phase 3→5)** | Tests for yfinance and FRED tool functions (no MCP) |
| `tests/test_mcp_client.py` | **Create (Phase 4)** | Tests for `MCPClient` with in-process fake server |

The server's `tools.py` is the part that's testable without MCP. `server.py` is a thin MCP wrapper. **Always put logic in `tools.py`, leave `server.py` dumb.**

---

# Phase 1: MCP concepts

> **What you'll learn:** What MCP is, the JSON-RPC shape, the three primitives, the `mcp` Python SDK layout.

No code yet. Three tasks. Each is reading + a tiny experiment.

## Task 1: Read the SDK source

**Files:** None (read-only).

- [ ] **Step 1: Install the official SDK**

Run: `uv pip install mcp`
Expected: installs `mcp` package; reports success.

- [ ] **Step 2: Find the SDK's server module**

Run: `python -c "import mcp.server; print(mcp.server.__file__)"`
Expected: prints the path to `mcp/server/__init__.py`.

- [ ] **Step 3: Skim the SDK's own examples**

Run: `ls $(python -c "import mcp, os; print(os.path.dirname(mcp.__file__))")/examples/`
Expected: a list of example servers. Open one and read it.

**What just happened:** You know where the SDK lives and what a server entry point looks like.

## Task 2: Write a one-line echo server

**Files:**
- Create: `/tmp/mcp_hello/server.py`

**Interfaces:** `mcp.server.Server` with one tool registered via `@server.list_tools()` and `@server.call_tool()` decorators.

- [ ] **Step 1: Create the file**

Write `/tmp/mcp_hello/server.py`:

```python
"""Minimal MCP server: one tool that echoes its argument."""
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("hello")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="echo",
            description="Return the input string verbatim.",
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name != "echo":
        raise ValueError(f"unknown tool: {name}")
    return [TextContent(type="text", text=arguments["text"])]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 2: Try it (it will hang — that's expected)**

Run: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"x","version":"1"}}"}' | python /tmp/mcp_hello/server.py`
Expected: prints an `initialize` response. Then it'll wait for more input — that's OK, kill it with Ctrl-C.

**What just happened:** You ran a real MCP server over stdio. The SDK did all the JSON-RPC framing for you; you wrote one tool handler.

## Task 3: Write the directory README

**Files:**
- Create: `mcp_servers/README.md`

- [ ] **Step 1: Create the file**

Write `mcp_servers/README.md`:

```markdown
# MCP Servers

Each subdirectory is a separate MCP server — a Python package that exposes
finance research tools to MCP clients (in our case, `mini_agent`) over
stdio.

## Servers

- `yfinance/` — stock prices, fundamentals, history (Phase 2-3)
- `fred/` — macro series from FRED (Phase 5)

## Layout

Every server has the same shape:

```
mcp_servers/<name>/
├── pyproject.toml     # installable as its own package
├── server.py          # MCP entry point — thin wrapper
└── tools.py           # pure-Python tool functions (testable without MCP)
```

The MCP layer (server.py) is dumb: it just registers tool handlers that
call into `tools.py`. Put your logic in `tools.py` so it's testable
without spinning up MCP.

## Running a server standalone

```
cd mcp_servers/yfinance && python -m server
```

It'll wait for JSON-RPC input on stdin. Use the MCP Inspector
(https://github.com/modelcontextprotocol/inspector) for a UI.
```

- [ ] **Step 2: Commit**

Commit message: `docs(mcp): add mcp_servers/ README`

**Phase 1 complete. You understand MCP at the protocol level and know where to look in the SDK. Stop here if you want; the remaining phases are all code.**

---

# Phase 2: First MCP server (stock prices)

> **What you'll learn:** How to structure an MCP server as a real package; how to register a tool with a yfinance call; how to run the server and verify it works.

## Task 4: Create the yfinance server package skeleton

**Files:**
- Create: `mcp_servers/yfinance/pyproject.toml`
- Create: `mcp_servers/yfinance/__init__.py` (empty)

**Interfaces:** A package named `mcp_yfinance` (or similar — pick a name not already in the registry), installable in editable mode.

- [ ] **Step 1: Create `pyproject.toml`**

Write `mcp_servers/yfinance/pyproject.toml`:

```toml
[project]
name = "mcp-yfinance"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0",
    "yfinance>=1.1",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = ["server", "tools"]
```

Note: `py-modules` (not `packages`) because the package is a flat directory, not a namespace package. The two module files (`server.py` and `tools.py`) sit at the top level.

- [ ] **Step 2: Create empty `__init__.py`**

```bash
touch mcp_servers/yfinance/__init__.py
```

- [ ] **Step 3: Install in editable mode**

Run: `cd mcp_servers/yfinance && uv pip install -e .`
Expected: installs `mcp-yfinance` in editable mode.

- [ ] **Step 4: Verify import works**

Run: `cd mcp_servers/yfinance && python -c "import yfinance; print(yfinance.__version__)"`
Expected: prints the yfinance version.

## Task 5: Write the first tool function

**Files:**
- Create: `mcp_servers/yfinance/tools.py`

**Interfaces:** `get_stock_price(ticker: str) -> str` — returns a one-line human-readable summary.

- [ ] **Step 1: Write the failing test**

Create `tests/test_mcp_servers.py`:

```python
"""Tests for MCP server tool implementations. No MCP here — pure Python."""

from unittest.mock import MagicMock, patch


def test_get_stock_price_returns_string():
    from mcp_servers.yfinance.tools import get_stock_price

    fake_info = {"shortName": "Apple Inc.", "regularMarketPrice": 150.25}
    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.info = fake_info
        result = get_stock_price("AAPL")

    assert isinstance(result, str)
    assert "Apple" in result
    assert "150.25" in result
```

Note: `tests/test_mcp_servers.py` lives at the repo root, not inside `mcp_servers/yfinance/`. The test imports the tool function across packages.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_servers.py -v`
Expected: ImportError because `mcp_servers/yfinance/tools.py` doesn't exist yet.

- [ ] **Step 3: Write `tools.py`**

Create `mcp_servers/yfinance/tools.py`:

```python
"""Pure-Python tool implementations for the yfinance MCP server.

These functions take simple Python inputs and return strings. They know
nothing about MCP — the server.py module wraps them in MCP handlers.
"""

import yfinance as yf


def get_stock_price(ticker: str) -> str:
    """Return the current market price for `ticker`."""
    t = yf.Ticker(ticker)
    info = t.info
    name = info.get("shortName") or info.get("longName") or ticker
    price = info.get("regularMarketPrice")
    if price is None:
        raise ValueError(f"No market price available for {ticker}")
    return f"{name} ({ticker}): ${price:.2f}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mcp_servers.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): scaffold yfinance server with get_stock_price tool`

**Phase 2 complete. You have a real MCP server with one tool.**

---

# Phase 3: Multi-tool yfinance server

> **What you'll learn:** How to register multiple tools; how to format large data (history) as a string; error handling.

## Task 6: Add `get_history` and `get_fundamentals`

**Files:**
- Modify: `mcp_servers/yfinance/tools.py`
- Test: `tests/test_mcp_servers.py`

**Interfaces:**
- `get_history(ticker: str, period: str = "1mo", interval: str = "1d") -> str`
- `get_fundamentals(ticker: str) -> str`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp_servers.py`:

```python
def test_get_history_returns_string():
    import pandas as pd
    from mcp_servers.yfinance.tools import get_history

    fake_df = pd.DataFrame(
        {"Close": [100.0, 101.5, 102.3]},
        index=pd.date_range("2024-01-01", periods=3),
    )
    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.history.return_value = fake_df
        result = get_history("AAPL", period="5d")

    assert isinstance(result, str)
    assert "AAPL" in result
    assert "102.3" in result


def test_get_fundamentals_returns_string():
    from mcp_servers.yfinance.tools import get_fundamentals

    fake_info = {
        "shortName": "Apple Inc.",
        "marketCap": 3000000000000,
        "trailingPE": 32.1,
        "dividendYield": 0.005,
    }
    with patch("yfinance.Ticker") as MockTicker:
        MockTicker.return_value.info = fake_info
        result = get_fundamentals("AAPL")

    assert isinstance(result, str)
    assert "Apple" in result
    assert "32.1" in result
    assert "0.5%" in result  # dividend yield formatted as percent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp_servers.py -v`
Expected: 2 failed with ImportError.

- [ ] **Step 3: Add the two functions to `tools.py`**

Modify `mcp_servers/yfinance/tools.py` — append below the existing `get_stock_price`:

```python
def get_history(ticker: str, period: str = "1mo", interval: str = "1d") -> str:
    """Return a text summary of recent price history."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No history available for {ticker} ({period})")
    last_close = float(df["Close"].iloc[-1])
    first_close = float(df["Close"].iloc[0])
    change_pct = (last_close - first_close) / first_close * 100
    return (
        f"{ticker} history ({period}, {interval}): "
        f"first ${first_close:.2f}, last ${last_close:.2f}, "
        f"change {change_pct:+.2f}%"
    )


def get_fundamentals(ticker: str) -> str:
    """Return a text summary of key fundamentals."""
    t = yf.Ticker(ticker)
    info = t.info
    name = info.get("shortName") or ticker
    mcap = info.get("marketCap")
    pe = info.get("trailingPE")
    dy = info.get("dividendYield")

    parts = [f"{name} ({ticker}) fundamentals:"]
    if mcap is not None:
        parts.append(f"  market cap: ${mcap / 1e9:.2f}B")
    if pe is not None:
        parts.append(f"  trailing P/E: {pe:.1f}")
    if dy is not None:
        parts.append(f"  dividend yield: {dy * 100:.2f}%")
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mcp_servers.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): add get_history and get_fundamentals to yfinance`

## Task 7: Wire tools into the MCP server

**Files:**
- Create: `mcp_servers/yfinance/server.py`

**Interfaces:** `mcp.server.Server` with three tools registered.

- [ ] **Step 1: Write `server.py`**

Create `mcp_servers/yfinance/server.py`:

```python
"""MCP server entry point for yfinance finance tools.

This is a thin wrapper. All logic lives in tools.py.
"""
import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools import get_stock_price, get_history, get_fundamentals


server = Server("yfinance")


_TOOL_DEFS = [
    Tool(
        name="get_stock_price",
        description="Get the current market price for a ticker symbol.",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_history",
        description=(
            "Get recent price history for a ticker. "
            "Use 'period' (e.g., '1mo', '1y') and 'interval' (e.g., '1d', '1wk')."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "period": {"type": "string", "default": "1mo"},
                "interval": {"type": "string", "default": "1d"},
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_fundamentals",
        description="Get key fundamentals (market cap, P/E, dividend yield) for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    ),
]


_TOOL_HANDLERS = {
    "get_stock_price": get_stock_price,
    "get_history": get_history,
    "get_fundamentals": get_fundamentals,
}


@server.list_tools()
async def list_tools():
    return _TOOL_DEFS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"unknown tool: {name}")
    result_str = handler(**arguments)
    return [TextContent(type="text", text=result_str)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Verify it starts**

Run: `cd mcp_servers/yfinance && timeout 2 python server.py < /dev/null; echo "exit=$?"`
Expected: prints JSON-RPC output or a clean exit (it'll hang waiting for input; `timeout 2` kills it). Exit code non-zero is fine here — we just want to see no Python errors at startup.

- [ ] **Step 3: Smoke test with a real query via Python**

```bash
cd mcp_servers/yfinance && python -c "
import asyncio, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command='python', args=['server.py'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print('Tools:', [t.name for t in tools.tools])
            result = await session.call_tool('get_stock_price', {'ticker': 'AAPL'})
            print('Result:', result.content[0].text)

asyncio.run(main())
"
```
Expected: prints `Tools: ['get_stock_price', 'get_history', 'get_fundamentals']` and a real Apple stock price string.

- [ ] **Step 4: Commit**

Commit message: `feat(mcp): wire yfinance tools into MCP server`

**Phase 3 complete. You have a 3-tool MCP server you can talk to from any MCP client.**

---

# Phase 4: MCP client in mini_agent

> **What you'll learn:** How to wrap an MCP subprocess client; how to adapt MCP tools into the existing `Tool` base class; how to wire it all together in `main.py`.

## Task 8: Define the `Tool` adapter

**Files:**
- Create: `mini_agent/mcp.py`
- Test: `tests/test_mcp_client.py`

**Interfaces:** `MCPToolAdapter(client: "MCPClient", name: str, description: str, parameters: dict)` — a `Tool` subclass whose `execute(arguments)` calls `client.call_tool(name, arguments)`.

- [ ] **Step 1: Write failing test**

Create `tests/test_mcp_client.py`:

```python
"""Tests for MCPClient and MCPToolAdapter."""

import asyncio
from unittest.mock import AsyncMock


def test_mcp_tool_adapter_execute_calls_client():
    from mini_agent.mcp import MCPToolAdapter

    fake_client = AsyncMock()
    fake_client.call_tool.return_value = "result-string"

    adapter = MCPToolAdapter(
        client=fake_client,
        name="get_stock_price",
        description="Get price",
        parameters={"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]},
    )

    out = adapter.execute({"ticker": "AAPL"})
    assert out == "result-string"

    # call_tool should have been awaited with (name, args)
    fake_client.call_tool.assert_called_once_with("get_stock_price", {"ticker": "AAPL"})

    # Adapter must satisfy the Tool contract (name/description/parameters)
    assert adapter.name == "get_stock_price"
    assert "Get price" in adapter.description
    assert adapter.parameters["type"] == "object"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mcp_client.py -v`
Expected: ImportError because `mini_agent/mcp.py` doesn't exist yet.

- [ ] **Step 3: Create `mini_agent/mcp.py` with just the adapter**

```python
"""MCP client integration.

Spawns MCP server subprocesses, discovers their tools, and adapts them
into mini_agent's Tool base class so they plug into the existing
ToolRegistry unchanged.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .tool import Tool

if TYPE_CHECKING:
    pass


class MCPToolAdapter(Tool):
    """Adapts an MCP-discovered tool to mini_agent's Tool interface.

    The MCP client is async; mini_agent's Tool.execute is sync. We
    bridge by running the coroutine to completion in a fresh event loop
    on each call. This is fine for low-frequency tool calls.
    """

    def __init__(
        self,
        client: "MCPClient",
        name: str,
        description: str,
        parameters: dict,
    ):
        self._client = client
        self._name = name
        self._description = description
        self._parameters = parameters

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return self._parameters

    def execute(self, arguments):
        coro = self._client.call_tool(self._name, arguments)
        return asyncio.run(coro)


class MCPClient:
    """Spawns an MCP server subprocess and talks to it over stdio.

    This is a placeholder — Task 9 fills in the actual implementation.
    """

    async def call_tool(self, name: str, arguments: dict) -> str:
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mcp_client.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): add MCPToolAdapter bridging async MCP client to sync Tool`

## Task 9: Implement `MCPClient` with subprocess + JSON-RPC

**Files:**
- Modify: `mini_agent/mcp.py` (replace the placeholder `MCPClient`)

**Interfaces:**
- `MCPClient(command: str, args: list[str])`
- `async MCPClient.connect()` — starts subprocess, initializes session
- `async MCPClient.list_tools() -> list[Tool]` — discovers and adapts
- `async MCPClient.call_tool(name, arguments) -> str` — calls and returns text
- `async MCPClient.disconnect()` — tears down

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp_client.py`:

```python
def test_mcp_client_with_in_process_fake_server():
    """Use a fake MCP server in-process — no subprocess needed."""
    from mini_agent.mcp import MCPClient

    client = MCPClient.__new__(MCPClient)  # bypass __init__ (no subprocess yet)
    client._session = _FakeSession()
    client._loop = asyncio.new_event_loop()

    async def run():
        tools = await client.list_tools()
        assert len(tools) == 2
        assert tools[0].name == "echo"
        result = await client.call_tool("echo", {"text": "hi"})
        assert result == "hi"
        await client.disconnect()

    asyncio.run(run())


class _FakeSession:
    """In-process fake of an MCP ClientSession."""

    async def initialize(self):
        pass

    async def list_tools(self):
        from mcp.types import Tool
        return type("ListResult", (), {
            "tools": [
                Tool(
                    name="echo",
                    description="Echo input",
                    inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                ),
                Tool(
                    name="ping",
                    description="Ping",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
            ],
        })()

    async def call_tool(self, name, arguments):
        from mcp.types import TextContent
        return type("CallResult", (), {
            "content": [TextContent(type="text", text=arguments.get("text", name))],
            "isError": False,
        })()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp_client.py -v`
Expected: test_mcp_client_with_in_process_fake_server fails.

- [ ] **Step 3: Replace `MCPClient` with the real implementation**

Replace the `MCPClient` class in `mini_agent/mcp.py`:

```python
class MCPClient:
    """Spawns an MCP server subprocess and proxies tool calls.

    Lifecycle: construct → `await connect()` → use → `await disconnect()`.
    """

    def __init__(self, command: str, args: list[str]):
        self._command = command
        self._args = args
        self._session = None
        self._stdio_context = None

    async def connect(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=self._command,
            args=self._args,
        )
        # stdio_client returns an async context manager yielding (read, write).
        # We hold the context open for the lifetime of the client.
        self._stdio_context = stdio_client(params)
        read_stream, write_stream = await self._stdio_context.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()

    async def disconnect(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._stdio_context is not None:
            await self._stdio_context.__aexit__(None, None, None)
            self._stdio_context = None

    async def list_tools(self) -> list[Tool]:
        if self._session is None:
            raise RuntimeError("MCPClient.connect() must be called first")
        result = await self._session.list_tools()
        return [
            MCPToolAdapter(
                client=self,
                name=t.name,
                description=t.description or "",
                parameters=t.inputSchema,
            )
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        if self._session is None:
            raise RuntimeError("MCPClient.connect() must be called first")
        result = await self._session.call_tool(name, arguments)
        if result.isError:
            raise RuntimeError(f"MCP tool '{name}' failed: {result.content}")
        # Concatenate text parts; tools typically return one.
        return "".join(
            piece.text for piece in result.content if hasattr(piece, "text")
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mcp_client.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): implement async MCPClient with subprocess stdio transport`

## Task 10: Wire MCP into `main.py`

**Files:**
- Modify: `mini_agent/main.py`

**Interfaces:** Two async helpers `setup_mcp_clients()` and `teardown_mcp_clients(clients)` that mini_agent's `main()` calls.

- [ ] **Step 1: Add the helpers and integrate**

Modify `mini_agent/main.py`. Three edits:

**Edit A** — Add import near the top:

```python
import asyncio

from .mcp import MCPClient
```

**Edit B** — Add two helpers anywhere before `def main():`:

```python
async def setup_mcp_clients():
    """Start MCP server subprocesses and return their clients."""
    clients = [
        MCPClient(
            command="python",
            args=["-m", "mcp_servers.yfinance.server"],
        ),
    ]
    started = []
    for client in clients:
        try:
            await client.connect()
            started.append(client)
        except Exception as e:
            print(f"[mcp] failed to start a server: {e}")
    return started


async def teardown_mcp_clients(clients):
    for client in clients:
        try:
            await client.disconnect()
        except Exception:
            pass
```

**Edit C** — Modify `def main():` to wrap the agent setup in `asyncio.run`:

```python
def main():
    # ... existing argparse and tool setup up to ToolRegistry ...

    registry = ToolRegistry(tools)

    # Connect MCP servers, register their tools
    mcp_clients = asyncio.run(setup_mcp_clients())
    try:
        for client in mcp_clients:
            mcp_tools = asyncio.run(client.list_tools())
            for tool in mcp_tools:
                registry.register(tool)

        # ... rest of the existing flow: build agent, run chat loop ...
    finally:
        asyncio.run(teardown_mcp_clients(mcp_clients))
```

Note: `asyncio.run` inside the chat loop would fail (nested loops). If you hit this during manual testing, the simplest fix is to wrap the chat loop's per-turn work in `asyncio.run` too. Defer the fix until discovered in Phase 6 smoke testing.

- [ ] **Step 2: Verify imports work**

Run: `python -c "from mini_agent.mcp import MCPClient, MCPToolAdapter; print('imports OK')"`
Expected: prints `imports OK`.

- [ ] **Step 3: Verify `--help` still works**

Run: `python -m mini_agent.main --help`
Expected: argparse help renders without import errors. (MCP setup happens at runtime, not at import time.)

- [ ] **Step 4: Run full test suite for regressions**

Run: `python -m pytest tests/ --ignore=tests/test_conditional_graph_routing.py -v`
Expected: 27+ tests pass (25 prior + 2 MCP client tests).

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): wire MCPClient into main.py tool registry`

**Phase 4 complete. `mini_agent` can spawn the yfinance server subprocess and use its tools.**

---

# Phase 5: FRED macro server

> **What you'll learn:** Building a second MCP server from scratch; using an API key from env; paginated responses.

This phase is a shorter repeat of Phases 2-3 with a new data source. Most of the structure is the same — copy the yfinance server, adapt for FRED.

## Task 11: Create the FRED server package

**Files:**
- Create: `mcp_servers/fred/pyproject.toml`
- Create: `mcp_servers/fred/__init__.py`
- Create: `mcp_servers/fred/tools.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "mcp-fred"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0",
    "fredapi>=0.5",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = ["server", "tools"]
```

- [ ] **Step 2: Create empty `__init__.py`**

```bash
touch mcp_servers/fred/__init__.py
```

- [ ] **Step 3: Install**

Run: `cd mcp_servers/fred && uv pip install -e .`

## Task 12: Write FRED tool functions

**Files:**
- Create: `mcp_servers/fred/tools.py`
- Test: `tests/test_mcp_servers.py` (extend)

**Interfaces:**
- `get_series(series_id: str, start: str = "", end: str = "") -> str`
- `search_series(query: str) -> str`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_mcp_servers.py`:

```python
def test_fred_get_series_returns_string():
    import pandas as pd
    from mcp_servers.fred.tools import get_series

    fake_df = pd.DataFrame(
        {"value": [4.0, 4.25, 4.5]},
        index=pd.date_range("2024-01-01", periods=3),
    )
    with patch("fredapi.Fred") as MockFred:
        MockFred.return_value.get_series.return_value = fake_df
        result = get_series("DGS10", start="2024-01-01")

    assert isinstance(result, str)
    assert "DGS10" in result
    assert "4.5" in result


def test_fred_search_series_returns_string():
    from mcp_servers.fred.tools import search_series

    with patch("fredapi.Fred") as MockFred:
        MockFred.return_value.search.return_value = pd.DataFrame({
            "id": ["DGS10", "DGS2"],
            "title": ["10-Year Treasury", "2-Year Treasury"],
        })
        result = search_series("treasury")

    assert isinstance(result, str)
    assert "DGS10" in result
    assert "DGS2" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp_servers.py -v -k "fred"`
Expected: ImportError.

- [ ] **Step 3: Write `tools.py`**

Create `mcp_servers/fred/tools.py`:

```python
"""Pure-Python tool implementations for the FRED MCP server."""

import os

import pandas as pd
from fredapi import Fred


def _client() -> Fred:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise ValueError("FRED_API_KEY environment variable is not set")
    return Fred(api_key=api_key)


def get_series(series_id: str, start: str = "", end: str = "") -> str:
    """Return a text summary of a FRED economic series."""
    kwargs = {}
    if start:
        kwargs["observation_start"] = start
    if end:
        kwargs["observation_end"] = end
    s = _client().get_series(series_id, **kwargs)
    if s is None or s.empty:
        raise ValueError(f"No data for FRED series {series_id}")
    last_date = s.index[-1].strftime("%Y-%m-%d")
    last_value = float(s.iloc[-1])
    return f"{series_id}: {last_value} (as of {last_date})"


def search_series(query: str) -> str:
    """Search FRED for series matching `query`."""
    df = _client().search(query)
    if df is None or df.empty:
        return f"No FRED series match '{query}'."
    lines = [f"FRED series matching '{query}':"]
    for _, row in df.head(10).iterrows():
        lines.append(f"  {row['id']}: {row['title']}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mcp_servers.py -v -k "fred"`
Expected: 2 passed.

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): scaffold FRED server with get_series and search_series tools`

## Task 13: Wire FRED into the MCP server

**Files:**
- Create: `mcp_servers/fred/server.py`

- [ ] **Step 1: Write `server.py`**

```python
"""MCP server entry point for FRED macro tools."""
import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools import get_series, search_series


server = Server("fred")


_TOOL_DEFS = [
    Tool(
        name="get_series",
        description="Get a FRED economic series (e.g., 'DGS10' for 10-year Treasury yield).",
        inputSchema={
            "type": "object",
            "properties": {
                "series_id": {"type": "string"},
                "start": {"type": "string", "default": ""},
                "end": {"type": "string", "default": ""},
            },
            "required": ["series_id"],
        },
    ),
    Tool(
        name="search_series",
        description="Search FRED for series matching a query.",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    ),
]


_TOOL_HANDLERS = {
    "get_series": get_series,
    "search_series": search_series,
}


@server.list_tools()
async def list_tools():
    return _TOOL_DEFS


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"unknown tool: {name}")
    result_str = handler(**arguments)
    return [TextContent(type="text", text=result_str)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Smoke test with real FRED API**

Set the env var (replace with your actual key): `export FRED_API_KEY=...`

```bash
cd mcp_servers/fred && python -c "
import asyncio, os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command='python', args=['server.py'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print('Tools:', [t.name for t in tools.tools])
            r = await session.call_tool('get_series', {'series_id': 'DGS10'})
            print('DGS10:', r.content[0].text)

asyncio.run(main())
"
```
Expected: prints tools and a real DGS10 value (something like `DGS10: 4.5 (as of YYYY-MM-DD)`).

- [ ] **Step 3: Wire FRED into `main.py`**

Modify `mini_agent/main.py`'s `setup_mcp_clients()` to add FRED:

```python
async def setup_mcp_clients():
    """Start MCP server subprocesses and return their clients."""
    clients = [
        MCPClient(command="python", args=["-m", "mcp_servers.yfinance.server"]),
        MCPClient(command="python", args=["-m", "mcp_servers.fred.server"]),
    ]
    started = []
    for client in clients:
        try:
            await client.connect()
            started.append(client)
        except Exception as e:
            print(f"[mcp] failed to start a server: {e}")
    return started
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest tests/ --ignore=tests/test_conditional_graph_routing.py -v`
Expected: 29+ tests pass (25 prior + 2 MCP client + 5 server).

- [ ] **Step 5: Commit**

Commit message: `feat(mcp): add FRED server and wire into mini_agent`

**Phase 5 complete. You have two MCP servers, each with multiple tools, integrated into mini_agent.**

---

# Phase 6: End-to-end verification

> **What you'll learn:** How to spot real-world integration bugs (env vars, nested asyncio, partial server failure).

This phase is mostly manual smoke testing. You'll find issues that didn't show up in unit tests — that's the point.

## Task 14: Run a real query end-to-end

**Files:** None.

- [ ] **Step 1: Verify env vars are set**

Run: `python -c "import os; print('OK' if os.environ.get('FRED_API_KEY') else 'FRED_API_KEY missing')"`
Expected: prints `OK`. If it prints `missing`, set the env var.

- [ ] **Step 2: Run the agent**

Run: `uv run mini-agent --engine graph`

- [ ] **Step 3: Try a real question**

Type: `what's NVDA's current PE ratio and how does it compare to the 10-year Treasury yield?`

Expected: the agent calls both yfinance (`get_fundamentals` for NVDA) and fred (`get_series` for DGS10), and returns a coherent comparison.

- [ ] **Step 4: Capture and document the trace

- Trace events from `traces.db` should show both MCP tool calls completing successfully.
- If either call fails, look at the error in the trace.

## Task 15: Document the directory structure

**Files:**
- Modify: `graph/graph_explain.md` (or create `mcp_servers/README.md` — already exists)

- [ ] **Step 1: Add a one-paragraph note about MCP to `graph/graph_explain.md`**

Find the section that lists files outside the graph package. Append a line about `mcp_servers/`.

- [ ] **Step 2: Commit**

Commit message: `docs(mcp): note MCP server integration in graph_explain.md`

**Phase 6 complete. The full system is end-to-end tested and documented.**

---

## Acceptance criteria (cross-cutting)

- [ ] All 6 phases completed.
- [ ] Test suite passes: ≥27 tests (25 prior + 2 MCP client + ≥5 server tests).
- [ ] `uv run mini-agent --engine graph` starts both servers.
- [ ] A real query about a stock price returns a real price via the yfinance server.
- [ ] A real query about a macro series returns a real value via the FRED server.
- [ ] All work uncommitted per user rule.

## Out of scope (deferred, post-v1)

- HTTP/SSE transport
- MCP resources and prompts
- Per-server authentication beyond env vars
- Production deployment (Docker, systemd, cloud)
- Web UI for browsing MCP tools
- Per-skill tools (Skills feature integration with MCP)
- Replacing existing built-in tools with MCP equivalents
- Connection pooling / multiple instances of the same server
- Auto-reconnect when a server subprocess crashes
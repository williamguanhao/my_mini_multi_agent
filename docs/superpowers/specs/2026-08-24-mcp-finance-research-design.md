# MCP for Finance Research — Design Spec

**Date:** 2026-08-24
**Status:** Draft
**Author:** (brainstormed with user)

## Purpose

Add **Model Context Protocol (MCP)** support to `mini_agent` so it can connect to standalone MCP servers that expose finance research tools. End state:

```
uv run mini-agent --engine graph
> what's NVDA's PE ratio and how does it compare to the 10-year Treasury yield?
[AgentLoop + GraphAgent → MCPClient → spawns subprocess for yfinance server + fred server]
[LLM calls yfinance.get_fundamentals("NVDA") → uses tool_executor.execute via MCP]
[LLM calls fred.get_series("DGS10", "2024") → uses tool_executor.execute via MCP]
mini_agent > NVDA's trailing PE is 65.4. The 10-year Treasury is currently 4.2%...
```

This spec establishes the **what** and the **why**. The phased implementation plan (separate doc) establishes the **how**, broken into six learning-oriented phases that each produce a working artifact.

## Goals

1. **Use the official Python MCP SDK** (`mcp` package on PyPI). Don't reimplement the protocol.
2. **Two finance MCP servers** in a separate `mcp_servers/` directory: yfinance (stock prices + fundamentals) and FRED (macro series).
3. **mini_agent becomes an MCP client.** A new `MCPClient` class spawns server subprocesses and integrates their tools into the existing `ToolRegistry`.
4. **Learning-oriented.** User has never used MCP. Phases teach concepts before code.

## Non-Goals

- HTTP/SSE transport (stdio only in v1)
- MCP resources and prompts (tools only)
- Server authentication beyond what the SDK provides
- Production deployment (Docker, systemd, etc.) — just local subprocess
- Replacing any existing built-in tools

## Concepts (teaching primer for the plan)

### What is MCP?

MCP is Anthropic's protocol for connecting AI agents to external tools. It's a **client-server JSON-RPC** protocol with three primitive types:

| Primitive | Who provides | Purpose |
|---|---|---|
| **Tools** | The server | Functions the agent can call (the main thing we'll use) |
| **Resources** | The server | Named data blobs the agent can read (e.g., files, configs) — **out of scope v1** |
| **Prompts** | The server | Pre-written prompt templates — **out of scope v1** |

A **client** (our agent) connects to a **server** (a finance tool provider), discovers what tools it offers, and calls them via JSON-RPC.

### Transport

The protocol runs over a transport. In v1 we use **stdio**: the client spawns the server as a subprocess and exchanges JSON-RPC messages line-by-line on stdin/stdout. Other transports (HTTP+SSE, Streamable HTTP) exist but stdio is the right starting point for a learning project.

### Message shape

Every message is a JSON object:

```json
// Client → Server: "what tools do you have?"
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

// Server → Client: "here are my tools"
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {"name": "get_stock_price", "description": "...", "inputSchema": {...}}
    ]
  }
}

// Client → Server: "call get_stock_price with these args"
{"jsonrpc": "2.0", "id": 2, "method": "tools/call",
 "params": {"name": "get_stock_price", "arguments": {"ticker": "NVDA"}}}
```

The SDK does the JSON-RPC framing for us; we just call high-level methods like `client.list_tools()` and `client.call_tool(name, args)`.

## Architecture

### New directory: `mcp_servers/`

```
mcp_servers/
├── README.md              ← what this directory is, how to add a server
├── yfinance/
│   ├── pyproject.toml     ← its own package, installable separately
│   ├── server.py          ← MCP server entrypoint
│   └── tools.py           ← tool implementations
└── fred/
    ├── pyproject.toml
    ├── server.py
    └── tools.py
```

Each server is its own installable Python package with a `server.py` that exposes an `mcp.server.Server` instance. Servers run as `python -m mcp_servers.yfinance.server` or similar.

### New module: `mini_agent/mcp.py`

A single `MCPClient` class. Responsibilities:

- Spawn a server subprocess (stdio transport)
- Initialize the MCP session
- Discover tools via `tools/list`
- Convert each MCP tool into a `mini_agent.tool.Tool` instance (the same `Tool` base class as built-in tools)
- Expose `connect()`, `disconnect()`, `list_tools()`, `call_tool()`

### Integration: `MCPClient` ↔ `ToolRegistry`

`main.py` (and any other entry point) gets a small new section:

```python
from mini_agent.mcp import MCPClient

async def setup_mcp_clients():
    clients = [
        MCPClient(command="python", args=["-m", "mcp_servers.yfinance.server"]),
        MCPClient(command="python", args=["-m", "mcp_servers.fred.server"]),
    ]
    for client in clients:
        await client.connect()
    return clients

async def teardown_mcp_clients(clients):
    for client in clients:
        await client.disconnect()

# In main():
clients = asyncio.run(setup_mcp_clients())
try:
    # ... build tools list including MCP-derived tools ...
    for client in clients:
        tools.extend(client.list_tools())
    # existing flow continues
finally:
    asyncio.run(teardown_mcp_clients(clients))
```

MCP-derived tools appear in the LLM's `tools=` parameter the same way built-in tools do. The agent doesn't know (or care) which tools came from where.

### The `Tool` adapter

`MCPClient.list_tools()` returns a list of `mini_agent.tool.Tool` instances. Each adapter's `execute(arguments)` calls `client.call_tool(name, arguments)` and returns the result as a string.

Why the adapter? Because:
1. The existing `ToolRegistry`, `Runtime`, and `AgentLoop` already know how to handle `Tool` instances. Zero changes to those.
2. The adapter encapsulates the async-MCP-bridge as a sync `execute()` call.
3. Tests can use a fake `Tool` without touching MCP at all.

## Data flow

```
User: "what's NVDA's PE ratio?"
  ↓
AgentLoop / ThinkNode (graph)
  ↓
model_client.generate(messages, tools=registry.schemas())
  ↓ (LLM decides to call)
  ↓
tool_executor.execute(tool_call)  # tool_call.function.name = "get_fundamentals"
  ↓
Runtime._parse_tool_call → tool.execute({"ticker": "NVDA", ...})
  ↓
MCP-Tool-Adapter.execute(arguments)
  ↓
asyncio.run(MCPClient.call_tool("get_fundamentals", arguments))
  ↓ (JSON-RPC over stdio to spawned subprocess)
  ↓
yfinance server: tools/call → yfinance.Ticker("NVDA").info → dict
  ↓
JSON-RPC response → adapter formats as string → tool.execute returns
  ↓
AgentLoop / ThinkNode: same flow as a built-in tool
```

The agent loop doesn't know this tool came from MCP. From its perspective, all tools are the same.

## File structure

| File | Status | Responsibility |
|---|---|---|
| `mini_agent/mcp.py` | **Create** | `MCPClient` class — stdio transport, tool discovery, call proxy, `Tool` adapter |
| `mini_agent/main.py` | **Modify** | Add `setup_mcp_clients()` / `teardown_mcp_clients()`, register MCP tools in the registry |
| `mcp_servers/README.md` | **Create** | What the directory is for, how to add a new server |
| `mcp_servers/yfinance/pyproject.toml` | **Create** | Package metadata, depends on `mcp` and `yfinance` |
| `mcp_servers/yfinance/server.py` | **Create** | MCP server entrypoint, registers tool handlers |
| `mcp_servers/yfinance/tools.py` | **Create** | `get_stock_price`, `get_fundamentals`, `get_history` implementations |
| `mcp_servers/fred/pyproject.toml` | **Create** | Package metadata, depends on `mcp` and `fredapi` |
| `mcp_servers/fred/server.py` | **Create** | MCP server entrypoint |
| `mcp_servers/fred/tools.py` | **Create** | `get_series`, `search_series` implementations |
| `tests/test_mcp_client.py` | **Create** | Tests for `MCPClient` with a fake subprocess |
| `tests/test_mcp_servers.py` | **Create** | Tests for tool implementations (no MCP, just Python) |

The tool implementations in `mcp_servers/yfinance/tools.py` are **pure Python** (call yfinance, format as string). The MCP layer (server.py) is a thin wrapper that registers those functions. This separation makes the tool code testable without spinning up MCP.

## Error handling

| Scenario | Behavior |
|---|---|
| Server subprocess fails to start | Log error, skip that server's tools, continue with others |
| `tools/list` returns nothing | Server is registered but has no tools — fine, just no tools from that source |
| Tool call raises in server subprocess | MCP returns an error response; `MCP-Tool-Adapter.execute()` re-raises so `Runtime.execute()` catches and wraps in `ToolResult(success=False, ...)` |
| Connection drops mid-call | `MCPClient.call_tool()` raises; same as above — runtime catches and wraps |
| FRED API key missing | Server fails to start with a clear error; logged at startup |
| yfinance rate-limit / no internet | Server's tool handler raises; propagates through MCP, caught by runtime |

## Testing strategy

Three layers, each independently testable:

1. **`tests/test_mcp_servers.py`** — imports `mcp_servers.yfinance.tools` directly and calls `get_stock_price(...)` with fakes (mock yfinance). No MCP, no subprocess. Pure unit tests for the tool logic.

2. **`tests/test_mcp_client.py`** — uses an in-process fake MCP server (just a Python class that implements the protocol methods without subprocess). Tests `MCPClient.connect()`, `list_tools()`, `call_tool()`. No yfinance, no real network.

3. **Manual end-to-end smoke test** — run `uv run mini-agent --engine graph`, ask a real finance question, watch the trace. Verified by the user interactively.

We deliberately skip "test the full MCP round-trip with a real subprocess" because it's slow and flaky. The layers above give us high confidence at low cost.

## Phased learning plan (separate doc)

The implementation is broken into 6 phases, each producing a working artifact. The phase doc (`docs/superpowers/plans/2026-08-24-mcp-finance-research.md`) covers:

1. **MCP concepts** — read the spec intro, run an echo server, see JSON-RPC on the wire
2. **First MCP server (stock prices)** — yfinance server with `get_stock_price`, run it standalone
3. **Multi-tool yfinance server** — add `get_fundamentals`, `get_history`, error handling
4. **MCP client in mini_agent** — `MCPClient` class, wire into `ToolRegistry`
5. **FRED macro server** — second server, real-world complexity (API key, pagination)
6. **End-to-end demo** — real question exercising both servers, polish

Each phase is independently runnable. If you stop after any phase, you have a working artifact.

## Migration / rollout

This is purely additive. No existing code is changed (other than `main.py` adding the MCP setup block). The existing `Agent` and `GraphAgent` continue to work; they just have more tools available when MCP servers are running.

If you don't want MCP at a given session, simply don't run the MCP servers — `main.py`'s setup is wrapped in try/except so missing servers degrade gracefully.

## Open questions

None at design time. Resolved in brainstorm:

- ✅ Both client + servers
- ✅ Official Python SDK
- ✅ FRED API key available
- ✅ Servers in `mcp_servers/` directory
- ✅ stdio transport only

## Acceptance criteria

- [ ] `mcp_servers/yfinance` can be started standalone and exposes at least 3 tools via MCP.
- [ ] `mcp_servers/fred` can be started standalone and exposes at least 2 tools via MCP.
- [ ] `mini_agent.MCPClient` connects to a server subprocess, discovers tools, and proxies calls.
- [ ] `MCPClient.list_tools()` returns `Tool` instances that work in `ToolRegistry`.
- [ ] End-to-end: asking `uv run mini-agent --engine graph` about a stock price triggers the yfinance server and returns the real price.
- [ ] End-to-end: asking about a macro series triggers the FRED server and returns the real value.
- [ ] All pre-existing tests still pass.
- [ ] `tests/test_mcp_client.py` and `tests/test_mcp_servers.py` pass.

## Out of scope (deferred)

- HTTP/SSE transport
- MCP resources and prompts
- Server-side authentication beyond env-var API keys
- Production deployment (Docker, cloud, systemd)
- Web UI for browsing MCP tools
- Per-skill tools (from the Skills feature)
- Replacing any existing built-in tool with an MCP equivalent
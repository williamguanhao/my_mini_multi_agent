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

The MCP layer (`server.py`) is dumb: it just registers tool handlers that
call into `tools.py`. Put your logic in `tools.py` so it's testable
without spinning up MCP.

## Running a server standalone

```
cd mcp_servers/yfinance && python -m server
```

It'll wait for JSON-RPC input on stdin. Use the MCP Inspector
(https://github.com/modelcontextprotocol/inspector) for a UI.

## Hello-world example

`/tmp/mcp_hello/server.py` (from Phase 1, Task 2) shows the minimum viable
MCP server: one `echo` tool, stdio transport. Useful as a template when
starting a new server.
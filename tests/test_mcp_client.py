"""Tests for MCPClient and MCPToolAdapter (sync API)."""

import asyncio
from unittest.mock import MagicMock


def test_mcp_tool_adapter_execute_calls_client():
    from mini_agent.mcp import MCPToolAdapter

    fake_client = MagicMock()
    fake_client.call_tool.return_value = "result-string"

    adapter = MCPToolAdapter(
        client=fake_client,
        name="get_stock_price",
        description="Get price",
        parameters={
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    )

    out = adapter.execute({'ticker': 'AAPL'})
    assert out == "result-string"

    fake_client.call_tool.assert_called_once_with(
        "get_stock_price", {'ticker': 'AAPL'}
    )

    assert adapter.name == "get_stock_price"
    assert "Get price" in adapter.description
    assert adapter.parameters["type"] == "object"


def test_mcp_client_with_in_process_fake_session():
    """Inject a fake session directly; use the real BackgroundLoop."""
    from mini_agent.mcp import MCPClient

    client = MCPClient.__new__(MCPClient)  # bypass __init__ (no real subprocess)
    client._command = "x"
    client._args = ["y"]
    client._cwd = None
    client._loop = _FakeLoop()
    client._session = _FakeSession()
    client._stdio_context = None

    tools = client.list_tools()
    assert len(tools) == 2
    assert tools[0].name == "echo"

    result = client.call_tool("echo", {"text": "hi"})
    assert result == "hi"


def test_mcp_client_connect_requires_session():
    """list_tools / call_tool without connect() should raise."""
    from mini_agent.mcp import MCPClient

    client = MCPClient.__new__(MCPClient)
    client._command = "x"
    client._args = ["y"]
    client._cwd = None
    client._loop = _FakeLoop()
    client._session = None
    client._stdio_context = None

    try:
        client.list_tools()
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "connect()" in str(e)

    try:
        client.call_tool("echo", {"text": "hi"})
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "connect()" in str(e)


class _FakeLoop:
    """Mimics BackgroundLoop: runs the coroutine via asyncio.run in the calling thread."""

    def run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class _FakeSession:
    """In-process fake of an MCP ClientSession. Returns Tool objects synchronously."""

    def list_tools(self):
        async def _list():
            from mcp.types import Tool as MCPTool
            return type("ListResult", (), {
                "tools": [
                    MCPTool(
                        name="echo",
                        description="Echo input",
                        inputSchema={
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        },
                    ),
                    MCPTool(
                        name="ping",
                        description="Ping",
                        inputSchema={"type": "object", "properties": {}, "required": []},
                    ),
                ],
            })()
        return _list()

    def call_tool(self, name, arguments):
        async def _call():
            from mcp.types import TextContent
            return type("CallResult", (), {
                "content": [TextContent(type="text", text=arguments.get("text", name))],
                "isError": False,
            })()
        return _call()
"""MCP server entry point for yfinance finance tools.

Uses MCP 1.x Server with @server.list_tools / @server.call_tool decorators.
"""
import asyncio

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
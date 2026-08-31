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
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
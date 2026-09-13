"""MCP server entry point for web search tools."""
import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from tools import web_search

server = Server("websearch")


_TOOL_DEFS = [
    Tool(
        name="web_search",
        description="Run a web search via the ddgs metasearch package. Returns top N results with title, URL, snippet.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    ),
]


_TOOL_HANDLERS = {
    "web_search": web_search,
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
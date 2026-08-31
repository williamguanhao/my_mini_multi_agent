"""MCP client integration.

Spawns MCP server subprocesses, discovers their tools, and adapts them
into mini_agent's Tool base class so they plug into the existing
ToolRegistry unchanged.

The async MCP SDK requires an event loop to be running for the lifetime
of the session (stdio streams + anyio cancel scopes are tied to one loop).
We bridge sync → async via a BackgroundLoop — a daemon thread running a
persistent event loop. Sync code calls `client.call_tool(name, args)`,
which dispatches the coroutine to the background loop via
`asyncio.run_coroutine_threadsafe` and blocks on the result.
"""

import asyncio
import threading

from .tool import Tool


class BackgroundLoop:
    """Persistent asyncio event loop running on a daemon thread.

    Provides `run(coro)` to execute coroutines from sync code, blocking
    until completion. All MCP async work for one client shares this
    loop, so the session's stdio streams and anyio cancel scopes stay
    coherent across multiple `connect()`/`list_tools()`/`call_tool()`
    invocations.
    """

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def run(self, coro):
        """Submit coro to the background loop and block for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def stop(self):
        """Stop the loop and join the thread (idempotent)."""
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except RuntimeError:
            pass  # already closed
        self._thread.join(timeout=5)


class MCPToolAdapter(Tool):
    """Adapts an MCP-discovered tool to mini_agent's sync Tool interface.

    Forwards `execute(arguments)` to the parent MCPClient, which bridges
    sync → async via its BackgroundLoop.
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
        return self._client.call_tool(self._name, arguments)


class MCPClient:
    """Spawns an MCP server subprocess and proxies tool calls.

    All public methods are sync. Async work runs on the client's
    BackgroundLoop, so the MCP session and stdio streams have a stable
    event loop for their entire lifetime.

    Lifecycle: construct → `connect()` → use → `disconnect()`.
    """

    def __init__(self, command: str, args: list[str], cwd: str | None = None):
        self._command = command
        self._args = args
        self._cwd = cwd
        self._loop = BackgroundLoop()
        self._session = None
        self._stdio_context = None

    def connect(self) -> None:
        """Spawn subprocess, open stdio, initialize MCP session."""
        self._loop.run(self._connect_async())

    async def _connect_async(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=self._command,
            args=self._args,
            cwd=self._cwd,
        )
        self._stdio_context = stdio_client(params)
        read_stream, write_stream = await self._stdio_context.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()

    def disconnect(self) -> None:
        """Tear down session, kill subprocess, stop the background loop."""
        try:
            self._loop.run(self._disconnect_async())
        finally:
            self._loop.stop()

    async def _disconnect_async(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._stdio_context is not None:
            await self._stdio_context.__aexit__(None, None, None)
            self._stdio_context = None

    def list_tools(self) -> list[Tool]:
        """Discover tools on the server and adapt each one."""
        if self._session is None:
            raise RuntimeError("MCPClient.connect() must be called first")
        result = self._loop.run(self._list_tools_async())
        return [
            MCPToolAdapter(
                client=self,
                name=t.name,
                description=t.description or "",
                parameters=t.inputSchema,
            )
            for t in result.tools
        ]

    async def _list_tools_async(self):
        return await self._session.list_tools()

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool by name. Returns the result as a string."""
        if self._session is None:
            raise RuntimeError("MCPClient.connect() must be called first")
        result = self._loop.run(self._call_tool_async(name, arguments))
        if result.isError:
            raise RuntimeError(f"MCP tool '{name}' failed: {result.content}")
        return "".join(
            piece.text for piece in result.content if hasattr(piece, "text")
        )

    async def _call_tool_async(self, name: str, arguments: dict):
        return await self._session.call_tool(name, arguments)
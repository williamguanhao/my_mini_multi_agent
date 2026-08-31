import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient():

    def __init__(
        self,
        command: str,
        args: list[str],
    ):
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
        )

    async def run(self):
        async with stdio_client(
            self.server_params
        ) as (read, write):

            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                tools = await session.list_tools()

                for tool in tools.tools:
                    print(
                        tool.name,
                        tool.description,
                    )

async def main():

    client = MCPClient(
        command="uv",
        args=[
            "run",
            "python",
            "server.py",
        ],
    )

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())

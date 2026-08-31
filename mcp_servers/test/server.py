from mcp.server.mcpserver import MCPServer

mcp = MCPServer("test Server")

@mcp.tool()
def search(query: str):
    return f"search resu;t {query}"

if __name__ == "__main__":
    mcp.run()
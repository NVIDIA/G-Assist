"""
G-Assist Plugin SDK

A simple SDK for building G-Assist plugins with automatic protocol handling.

Basic Plugin Example:
    from gassist_sdk import Plugin, command

    plugin = Plugin("my-plugin", version="1.0.0")

    @plugin.command("search")
    def search(query: str):
        plugin.stream("Searching...")
        return {"results": do_search(query)}

    if __name__ == "__main__":
        plugin.run()

MCP Plugin Example (auto-discovery from MCP servers):
    from gassist_sdk import MCPPlugin
    from gassist_sdk.mcp import MCPClient, FunctionDef, sanitize_name

    plugin = MCPPlugin(
        name="stream-deck",
        version="1.0.0",
        mcp_url="http://localhost:9090/mcp"
    )

    @plugin.discoverer
    def discover_actions(mcp: MCPClient) -> List[FunctionDef]:
        result = mcp.call_tool("get_executable_actions")
        return [
            FunctionDef(
                name=sanitize_name(f"streamdeck_{a['title']}"),
                description=f"Execute '{a['title']}'",
                executor=lambda aid=a['id']: mcp.call_tool("execute_action", {"id": aid})
            )
            for a in result.get("actions", [])
        ]

    if __name__ == "__main__":
        plugin.run()  # Auto-discovers at startup

MCP Spec: https://modelcontextprotocol.io/specification/2025-06-18
"""

from .plugin import Plugin, MCPPlugin, command
from .types import Context, SystemInfo, CommandResult
from .protocol import ProtocolError, ConnectionClosed
from .mcp import (
    MCPClient,
    MCPError,
    MCPTransport,
    StdioTransport,
    HTTPTransport,
    FunctionDef,
    FunctionRegistry,
    sanitize_name,
    HAS_REQUESTS,
)

__version__ = "3.0.0"
__all__ = [
    # Core Plugin
    "Plugin",
    "MCPPlugin",
    "command",
    # Types
    "Context",
    "SystemInfo",
    "CommandResult",
    # Protocol Errors
    "ProtocolError",
    "ConnectionClosed",
    # MCP Client
    "MCPClient",
    "MCPError",
    "MCPTransport",
    "StdioTransport",
    "HTTPTransport",
    # MCP Discovery
    "FunctionDef",
    "FunctionRegistry",
    "sanitize_name",
    "HAS_REQUESTS",
]


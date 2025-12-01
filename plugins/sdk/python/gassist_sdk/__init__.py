"""
G-Assist Plugin SDK

A simple SDK for building G-Assist plugins with automatic protocol handling.

Example:
    from gassist_sdk import Plugin, command

    plugin = Plugin("my-plugin", version="1.0.0")

    @plugin.command("search")
    def search(query: str):
        plugin.stream("Searching...")
        return {"results": do_search(query)}

    if __name__ == "__main__":
        plugin.run()
"""

from .plugin import Plugin, command
from .types import Context, SystemInfo, CommandResult
from .protocol import ProtocolError, ConnectionClosed

__version__ = "2.0.0"
__all__ = [
    "Plugin",
    "command", 
    "Context",
    "SystemInfo",
    "CommandResult",
    "ProtocolError",
    "ConnectionClosed",
]


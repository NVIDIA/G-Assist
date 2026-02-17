"""
MCP Stdio Filesystem Plugin — G-Assist

Demonstrates how to build a G-Assist plugin that:
  1. Spawns an *existing* MCP server as a subprocess over stdio.
  2. Communicates with it via newline-delimited JSON-RPC 2.0 (MCP stdio transport).
  3. Auto-discovers every tool the server exposes at startup.
  4. Registers each tool as a G-Assist command and forwards invocations.

The MCP server used here is the official reference implementation
``@modelcontextprotocol/server-filesystem`` (Node.js) which provides
safe file-system operations scoped to allowed directories:

    read_file, read_multiple_files, write_file, edit_file,
    list_directory, directory_tree, move_file, search_files,
    get_file_info, list_allowed_directories, create_directory

Prerequisites:
    Node.js >= 18  (provides npx)

Usage:
    The G-Assist engine launches this plugin via its manifest.  During
    development you can test with the plugin_emulator.
"""

import json
import logging
import os
import shutil
import sys
import warnings
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# IMPORTANT: The G-Assist engine (and plugin_emulator) merge stderr into
# stdout (stderr=subprocess.STDOUT).  Any stray text on stderr corrupts the
# binary length-prefixed protocol.  We redirect stderr to a log file before
# importing anything that might emit warnings (e.g. urllib3).
# ---------------------------------------------------------------------------
warnings.filterwarnings("ignore")  # suppress Python warnings to stderr

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_stderr_log = os.path.join(_plugin_dir, "stderr.log")
try:
    sys.stderr = open(_stderr_log, "w")
except OSError:
    sys.stderr = open(os.devnull, "w")

# ---------------------------------------------------------------------------
# SDK import — the engine adds libs/ to sys.path automatically;
# we also add it here so the plugin works during local development.
# ---------------------------------------------------------------------------
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

try:
    from gassist_sdk import MCPPlugin, Context
    from gassist_sdk.mcp import (
        MCPClient,
        StdioTransport,
        FunctionDef,
        sanitize_name,
    )
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.stderr.write("Ensure gassist_sdk is in the libs/ folder.\n")
    sys.stderr.flush()
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PLUGIN_NAME = "mcp-stdio-filesystem"
PLUGIN_VERSION = "1.0.0"

# Directories the MCP filesystem server is allowed to operate on.
# Override via environment variable (comma-separated for multiple dirs).
ALLOWED_DIRS = os.environ.get(
    "MCP_FS_ALLOWED_DIRS",
    os.path.join(os.path.expanduser("~"), "Documents"),
).split(",")

# Resolve npx — the official MCP filesystem server is a Node.js package.
NPX_CMD = shutil.which("npx")
if NPX_CMD is None:
    sys.stderr.write("FATAL: npx not found. Install Node.js >= 18.\n")
    sys.stderr.flush()
    sys.exit(1)

# Logging
LOG_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", _plugin_dir),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME,
)
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, f"{PLUGIN_NAME}.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Build the stdio transport command
# ---------------------------------------------------------------------------

def _build_server_command() -> List[str]:
    """
    Build the command to spawn the official MCP filesystem server.

    npx -y @modelcontextprotocol/server-filesystem <dir1> [dir2] ...

    The server communicates over stdio with newline-delimited JSON-RPC 2.0.
    """
    cmd = [NPX_CMD, "-y", "@modelcontextprotocol/server-filesystem"]
    cmd.extend([d.strip() for d in ALLOWED_DIRS])
    return cmd

server_command = _build_server_command()
logger.info(f"MCP server command: {server_command}")

# ---------------------------------------------------------------------------
# Create the stdio transport and MCPPlugin
# ---------------------------------------------------------------------------
stdio_transport = StdioTransport(
    command=server_command,
    env={"PYTHONUNBUFFERED": "1"},
)

plugin = MCPPlugin(
    name=PLUGIN_NAME,
    version=PLUGIN_VERSION,
    description=(
        "G-Assist plugin that connects to mcp-server-filesystem over stdio, "
        "providing file read/write/edit/list/move/delete operations."
    ),
    mcp_transport=stdio_transport,
    poll_interval=0,              # static tool set — no need to poll
    auto_refresh_session=False,   # stdio doesn't use sessions
    source_dir=_plugin_dir,
)


# ---------------------------------------------------------------------------
# Discovery — convert MCP tools into G-Assist commands
#
# We register each MCP tool as a plugin command directly (via
# plugin._commands) so that runtime arguments flow through correctly.
# The SDK's default FunctionDef.executor pattern uses zero-arg closures,
# which doesn't work for tools that need runtime parameters like file paths.
# ---------------------------------------------------------------------------
from gassist_sdk.plugin import CommandInfo  # for direct registration


@plugin.discoverer
def discover_tools(mcp: MCPClient) -> List[FunctionDef]:
    """
    Called once at startup.  Lists every tool the MCP filesystem server
    exposes and registers each as a G-Assist command.

    We register commands directly (via plugin._commands) so that runtime
    arguments (e.g. file paths) are forwarded to the MCP server correctly.
    The SDK's built-in FunctionDef.executor pattern uses zero-arg closures
    which doesn't work for tools that need runtime parameters.

    Returns an empty list so the SDK's _register_discovered_functions
    doesn't overwrite our registrations.  We update the function registry
    manually for caching and manifest generation.
    """
    tools = mcp.list_tools()
    logger.info(f"Discovered {len(tools)} tools from mcp-server-filesystem")

    for tool in tools:
        tool_name: str = tool["name"]
        tool_desc: str = tool.get("description", "")
        schema: Dict[str, Any] = tool.get("inputSchema", {})

        # Build parameter metadata for the G-Assist manifest
        properties: Dict[str, Any] = {}
        required: List[str] = schema.get("required", [])
        for prop_name, prop_def in schema.get("properties", {}).items():
            properties[prop_name] = {
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", ""),
            }

        # Create a command handler that accepts **kwargs and forwards
        # all runtime arguments to the MCP server.  JSON-serialize the
        # result because the engine/emulator expects strings.
        def make_handler(name: str):
            def handler(**kwargs):
                logger.info(f"Calling MCP tool '{name}' with args: {kwargs}")
                result = mcp.call_tool(name, kwargs)
                if isinstance(result, dict):
                    return json.dumps(result, indent=2)
                return str(result)
            return handler

        cmd_name = sanitize_name(tool_name)

        # Register directly as a plugin command
        plugin._commands[cmd_name] = CommandInfo(
            name=cmd_name,
            handler=make_handler(tool_name),
            description=tool_desc,
        )

        # Register in the function registry (for manifest/cache)
        plugin._registry.register(FunctionDef(
            name=cmd_name,
            description=tool_desc,
            tags=[cmd_name, "filesystem", "mcp", "stdio"],
            properties=properties,
            required=required,
        ))

    # Save cache and update manifest
    plugin._registry.save_cache()
    plugin._registry.update_manifest(PLUGIN_VERSION, plugin.description)

    # Return empty so the SDK doesn't overwrite our command registrations
    return []


# ---------------------------------------------------------------------------
# Static utility commands (mixed alongside auto-discovered tools)
# ---------------------------------------------------------------------------
@plugin.command("plugin_status")
def plugin_status(context: Context = None):
    """
    Show the plugin status, connected MCP server info, and project directory.
    """
    server = plugin.mcp.server_info if plugin.mcp else None
    return json.dumps({
        "plugin": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "allowed_dirs": ALLOWED_DIRS,
        "mcp_server": server.name if server else "not connected",
        "mcp_server_version": server.version if server else "n/a",
        "discovered_commands": list(plugin._commands.keys()),
    }, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} v{PLUGIN_VERSION}")
    logger.info(f"Allowed directories: {ALLOWED_DIRS}")
    plugin.run()

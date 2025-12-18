# G-Assist Plugin SDK

A Python SDK for building G-Assist plugins with:
- **Protocol V2** (JSON-RPC 2.0) for engine communication
- **Full MCP support** ([Model Context Protocol](https://modelcontextprotocol.io/specification/2025-06-18)) for connecting to MCP servers
- **Auto-discovery** and dynamic function registration

## Installation

```bash
pip install .
```

Or for development:
```bash
pip install -e .
```

For MCP HTTP transport support:
```bash
pip install requests
```

## Quick Start

### Basic Plugin

```python
from gassist_sdk import Plugin

# Create a plugin
plugin = Plugin("my-plugin", version="1.0.0")

# Register commands using decorators
@plugin.command("search_web")
def search_web(query: str):
    """Search the web for information."""
    plugin.stream("Searching...")  # Send streaming update
    results = do_search(query)
    return {"results": results}

@plugin.command("get_weather")
def get_weather(location: str):
    """Get weather for a location."""
    return get_weather_data(location)

# Start the plugin
if __name__ == "__main__":
    plugin.run()
```

### MCP Plugin (Auto-Discovery)

Connect to MCP servers and auto-discover functions:

```python
from gassist_sdk import MCPPlugin
from gassist_sdk.mcp import FunctionDef, sanitize_name

# Create plugin with MCP server configuration
plugin = MCPPlugin(
    name="stream-deck",
    version="1.0.0",
    mcp_url="http://localhost:9090/mcp",
    discovery_timeout=5.0  # Quick timeout for startup
)

# Define how to discover functions from the MCP server
@plugin.discoverer
def discover_actions(mcp):
    """Called at startup and on rediscover()."""
    result = mcp.call_tool("get_executable_actions")
    
    functions = []
    for action in result.get("actions", []):
        action_id = action["id"]
        title = action["title"]
        
        functions.append(FunctionDef(
            name=sanitize_name(f"streamdeck_{title}"),
            description=f"Execute '{title}' on Stream Deck",
            tags=["stream-deck", "execute"],
            executor=lambda aid=action_id: mcp.call_tool("execute_action", {"id": aid})
        ))
    
    return functions

# Static commands (always available)
@plugin.command("streamdeck_discover")
def discover_cmd():
    """Re-discover Stream Deck actions."""
    count = plugin.rediscover()
    return f"Discovered {count} actions"

@plugin.command("streamdeck_refresh")
def refresh_cmd():
    """Refresh connection."""
    if plugin.refresh_session():
        return "Connection refreshed"
    return "Failed to refresh"

if __name__ == "__main__":
    plugin.run()  # Auto-discovers at startup!
```

## Features

### Automatic Protocol Handling

The SDK handles all protocol details:
- Message framing (length-prefixed)
- JSON-RPC 2.0 communication
- Ping/pong responses (automatic!)
- Error handling and reporting
- Graceful shutdown

### No Threading Required!

Unlike manual plugin implementations, you don't need to manage heartbeat threads. The SDK handles ping/pong automatically in the main loop.

### Streaming Support

Send partial results during long operations:

```python
@plugin.command("analyze")
def analyze(data: str):
    plugin.stream("Starting analysis...")
    
    for i, step in enumerate(analysis_steps):
        result = step.run(data)
        plugin.stream(f"Step {i+1} complete: {result}")
    
    return {"analysis": final_result}
```

### Passthrough Mode

Keep the session open for follow-up questions:

```python
@plugin.command("chat")
def chat(query: str):
    response = generate_response(query)
    plugin.set_keep_session(True)  # Stay in passthrough mode
    return response

@plugin.command("on_input")
def on_input(content: str):
    """Handle follow-up user input."""
    response = generate_response(content)
    plugin.set_keep_session(True)
    return response
```

### Context Access

Access conversation history and system info:

```python
@plugin.command("contextual_search")
def contextual_search(query: str, context: Context, system_info: SystemInfo):
    # Get last user message
    last_message = context.last_user_message()
    
    # Access full history
    for msg in context.messages:
        print(f"{msg.role}: {msg.content}")
    
    return do_search(query)
```

## MCP (Model Context Protocol)

The SDK implements the [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18) for connecting to MCP servers.

### MCPClient Direct Usage

Use MCPClient directly for custom integrations:

```python
from gassist_sdk.mcp import MCPClient

# Connect to MCP server
mcp = MCPClient(url="http://localhost:9090/mcp")

if mcp.connect():
    # List available tools
    tools = mcp.list_tools()
    
    # Call a tool
    result = mcp.call_tool("my_tool", {"arg": "value"})
    
    # List resources (if server supports)
    resources = mcp.list_resources()
    
    # Read a resource
    content = mcp.read_resource("file:///path/to/resource")
    
    # Clean disconnect
    mcp.disconnect()
```

### Transports

MCP supports multiple transports:

```python
from gassist_sdk.mcp import MCPClient, StdioTransport, HTTPTransport

# HTTP Transport (for network MCP servers)
http_transport = HTTPTransport(
    url="http://localhost:9090/mcp",
    timeout=30.0,
    session_timeout=300.0  # Refresh session after 5min idle
)
mcp = MCPClient(transport=http_transport)

# Stdio Transport (for subprocess MCP servers)
stdio_transport = StdioTransport(
    command=["node", "mcp-server.js"],
    env={"NODE_ENV": "production"}
)
mcp = MCPClient(transport=stdio_transport)
```

### Session Management

The SDK handles MCP session lifecycle automatically:
- Sessions are initialized on first `connect()`
- Stale sessions (idle > timeout) are auto-refreshed
- HTTP errors (400/401/403) trigger session refresh
- Cached functions work offline when server unavailable

### MCP Manifest Schema

MCP plugins declare their configuration in `manifest.json`:

```json
{
  "manifestVersion": 1,
  "name": "stream-deck",
  "version": "2.0.0",
  "description": "Stream Deck plugin",
  "executable": "plugin.py",
  "persistent": true,
  "protocol_version": "2.0",
  "mcp": {
    "enabled": true,
    "server_url": "http://localhost:9090/mcp",
    "launch_on_startup": true
  },
  "functions": []
}
```

When `launch_on_startup` is `true`:
1. Engine launches the plugin at startup
2. Plugin connects to MCP server and discovers functions
3. Plugin writes updated manifest with discovered functions
4. Engine re-reads manifest to pick up new functions

This eliminates the need for "bootstrap" functions - the manifest starts empty
and is populated by auto-discovery.

### FunctionDef

Define discovered functions:

```python
from gassist_sdk.mcp import FunctionDef, sanitize_name

func = FunctionDef(
    name=sanitize_name("My Action"),  # -> "my_action"
    description="Execute my action",
    tags=["action", "execute"],
    executor=lambda: mcp.call_tool("execute", {"id": "123"}),
    properties={"arg": {"type": "string"}},  # For manifest
    required=["arg"]
)
```

## API Reference

### Plugin Class

```python
Plugin(
    name: str,           # Plugin name (must match manifest.json)
    version: str,        # Plugin version
    description: str,    # Plugin description
)
```

#### Methods

- `plugin.command(name, description)` - Decorator to register a command
- `plugin.stream(data)` - Send streaming data
- `plugin.log(message, level)` - Send log message
- `plugin.set_keep_session(keep)` - Set passthrough mode
- `plugin.run()` - Start the plugin main loop

### MCPPlugin Class

Extends Plugin with MCP auto-discovery:

```python
MCPPlugin(
    name: str,                    # Plugin name
    version: str,                 # Plugin version
    description: str,             # Plugin description
    mcp_url: str,                 # MCP server URL
    mcp_transport: MCPTransport,  # Custom transport (alternative to URL)
    mcp_timeout: float = 30.0,    # Request timeout
    session_timeout: float = 300.0,  # Session idle timeout
    discovery_timeout: float = 5.0,  # Startup discovery timeout
    base_functions: List[dict],   # Static functions for manifest
)
```

#### Methods (in addition to Plugin)

- `plugin.discoverer` - Decorator to register discovery function
- `plugin.mcp` - Property to access MCPClient
- `plugin.refresh_session()` - Force session refresh
- `plugin.rediscover()` - Re-run discovery, returns function count

### MCPClient Class

```python
MCPClient(
    transport: MCPTransport,     # Transport layer
    url: str,                    # HTTP URL (creates HTTPTransport)
    timeout: float = 30.0,       # Request timeout
    session_timeout: float = 300.0,
    client_name: str,            # For MCP handshake
    client_version: str,
)
```

#### Methods

- `mcp.connect(startup_timeout)` - Initialize session
- `mcp.disconnect()` - Clean shutdown
- `mcp.list_tools()` - List available tools
- `mcp.call_tool(name, arguments)` - Call a tool
- `mcp.list_resources()` - List resources (if supported)
- `mcp.read_resource(uri)` - Read a resource
- `mcp.list_prompts()` - List prompts (if supported)
- `mcp.get_prompt(name, arguments)` - Get a prompt

#### Properties

- `mcp.is_connected` - Check connection status
- `mcp.server_info` - Server info from initialization

### Context Class

```python
context.messages        # List of Message objects
context.last_user_message()  # Get last user message content
context.to_list()       # Convert to list of dicts
```

### LogLevel Enum

```python
LogLevel.DEBUG
LogLevel.INFO
LogLevel.WARNING
LogLevel.ERROR
```

## Protocol Versions

### V2 (Default)

Uses JSON-RPC 2.0 with length-prefixed framing. Recommended for new plugins.

### V1 (Legacy)

Uses plain JSON with `<<END>>` delimiter. For backwards compatibility:

```python
plugin = Plugin("my-plugin", use_legacy_protocol=True)
```

## Examples

See the `plugins/examples/` directory for complete plugin examples:

- `hello-world/` - Simple example demonstrating basic commands, streaming, and passthrough
- `gemini/` - Production plugin with API integration, setup wizard, and streaming

## Manifest File

Create a `manifest.json` alongside your plugin:

```json
{
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "My awesome plugin",
    "author": "Your Name",
    "main": "plugin.py",
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "search_web",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
                "required": ["query"]
            }
        }
    ]
}
```

## Troubleshooting

### Plugin not responding

Check `plugin_sdk.log` in the SDK directory for error messages.

### Commands not found

Ensure command names in `manifest.json` match the `@plugin.command()` decorator names.

### Connection errors

Make sure you're not printing to stdout - use `plugin.stream()` instead.


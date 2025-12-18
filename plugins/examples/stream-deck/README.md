# Stream Deck Plugin

A G-Assist plugin that integrates with **Elgato Stream Deck** via an MCP (Model Context Protocol) server. This plugin discovers your configured Stream Deck actions and lets you execute them with natural language.

**Version 2.0.0** - Now using the SDK's `MCPPlugin` for simplified MCP integration.

## Features

- **SDK-Based MCP**: Uses the G-Assist SDK's built-in MCP client for clean, reliable connections
- **Auto-Discovery**: Automatically discovers all Stream Deck actions at startup
- **Dynamic Functions**: Each discovered action becomes a callable function
- **Natural Language**: Execute actions by simply asking (e.g., "open the webpage" or "play the audio")
- **Session Management**: Automatic session lifecycle, refresh, and error recovery
- **Offline Caching**: Works with cached actions when MCP server is temporarily unavailable

## Prerequisites

1. **Stream Deck MCP Server** running at `http://localhost:9090/mcp`
2. **Python 3.x** with `requests` library
3. **Stream Deck** with configured actions (buttons)

## Quick Start

### 1. Setup

From the `plugins/examples/` folder:

```batch
setup.bat stream-deck
```

### 2. Configure

Edit `config.json` to set your MCP server URL:

```json
{
  "mcp_server_url": "http://localhost:9090/mcp",
  "timeout": 30
}
```

### 3. Deploy

```batch
setup.bat stream-deck -deploy
```

### 4. Use

In G-Assist, just ask to execute Stream Deck actions:

- "Open the webpage"
- "Play the audio"
- "Start the timer"

**No manual discovery needed!** The plugin auto-discovers actions at startup.

## How It Works

### Auto-Discovery at Startup

When the plugin starts, it automatically:
1. Tries to connect to the Stream Deck MCP server (5-second timeout)
2. If connected: discovers all executable actions and updates the manifest
3. If not connected: uses cached actions from previous discovery
4. Registers all discovered actions as callable functions

This means **users can immediately use their Stream Deck actions** without manually calling `streamdeck_discover` first.

### Manual Discovery (Optional)

Use `streamdeck_discover` to:
- Force refresh of available actions after adding new buttons
- See a list of all available actions
- Reconnect if the MCP server was restarted

### Example Discovery Output

```
Discovering Stream Deck...

Connecting to Stream Deck MCP server...
Connected.

Querying available actions...
Found 4 actions.

Registering actions...
Done.

Stream Deck Discovery Complete

Found 4 actions ready to use:

- Open webpage (Website) - Open URL
- Play Video (Play Audio) - Play a sound bite, audio effect or music clip
- Audacity (Open Application) - Open an app
- Timer - Timer for Stream Deck (acoustically and visually)

Just ask me to execute any of these actions.
```

### Action Execution

After discovery, simply ask to execute any action:

- "Execute the timer"
- "Open webpage"
- "Play the video"

## Commands

| Command | Description |
|---------|-------------|
| `streamdeck_discover` | Connect to Stream Deck and discover available actions |
| `streamdeck_refresh` | Refresh the connection (clears cached session) |
| `streamdeck_<action>` | (Dynamic) Execute a discovered action |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `mcp_server_url` | `http://localhost:9090/mcp` | MCP server endpoint |
| `timeout` | `30` | Request timeout in seconds |
| `session_timeout` | `300` | Session idle timeout in seconds (auto-refresh if idle longer) |

## Session Management

The plugin includes robust session management to prevent stale session issues:

- **Automatic refresh**: Sessions are automatically refreshed if idle for more than `session_timeout` seconds (default 5 minutes)
- **Error recovery**: HTTP 400/401/403 errors automatically trigger session re-initialization
- **Manual refresh**: Use `streamdeck_refresh` to force a fresh connection
- **Discovery refresh**: `streamdeck_discover` always starts with a fresh session to ensure accurate results

## Architecture

This plugin uses the SDK's `MCPPlugin` class which provides:
- Automatic MCP connection and session management
- Built-in function discovery via `@plugin.discoverer` decorator
- Manifest updates with discovered functions
- Caching of discovered functions for offline use

### MCP Manifest Schema

The manifest declares this as an MCP plugin:

```json
{
  "mcp": {
    "enabled": true,
    "server_url": "http://localhost:9090/mcp",
    "launch_on_startup": true
  },
  "functions": []
}
```

When `launch_on_startup` is `true`, the engine launches this plugin at startup,
allowing it to discover functions and populate the manifest automatically.

### Discovery Function

```python
@plugin.discoverer
def discover_actions(mcp: MCPClient) -> List[FunctionDef]:
    result = mcp.call_tool("get_executable_actions")
    return [
        FunctionDef(
            name=sanitize_name(f"streamdeck_{a['title']}"),
            description=f"Execute '{a['title']}' on Stream Deck",
            executor=lambda aid=a['id']: mcp.call_tool("execute_action", {"id": aid})
        )
        for a in result.get("actions", [])
    ]
```

## Files

```
stream-deck/
├── plugin.py                    # Main plugin (uses MCPPlugin from SDK)
├── manifest.json                # Function definitions (updated on discovery)
├── config.json                  # MCP server configuration
├── requirements.txt             # Python dependencies
├── libs/gassist_sdk/            # G-Assist SDK
│   ├── __init__.py
│   ├── plugin.py                # Plugin + MCPPlugin classes
│   ├── mcp.py                   # MCP client, transports, FunctionDef
│   ├── protocol.py              # Engine protocol
│   └── types.py                 # Data types
└── README.md                    # This file
```

At runtime, the SDK creates:
- `discovered_functions.json` - Cached discovered functions

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\stream-deck\stream-deck.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Failed to connect to Stream Deck MCP server" | Ensure MCP server is running at the configured URL |
| "No executable actions found" | Configure some actions on your Stream Deck first |
| Discovered actions not working | Run discovery again after adding new Stream Deck actions |
| Connection timeout | Increase `timeout` in config.json |

## MCP Server

This plugin requires an MCP server that provides:
- `initialize` - Start a session
- `tools/list` - List available tools (including `get_executable_actions`)
- `tools/call` - Execute tools (including `execute_action`)

See the Stream Deck MCP server documentation for setup instructions.

## License

Apache License 2.0

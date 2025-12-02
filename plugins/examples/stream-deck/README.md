# Stream Deck MCP Plugin

A G-Assist plugin that interfaces with the **Elgato Stream Deck** via an MCP (Model Context Protocol) server. This plugin dynamically discovers available tools from the MCP server and updates its manifest at runtime.

## Features

- **Dynamic Tool Discovery**: Queries the MCP server for available tools and updates the manifest
- **Generic Tool Calling**: Call any MCP tool by name with JSON arguments
- **Session Management**: Handles MCP session initialization and persistence
- **Auto-Discovery**: Optionally discover tools on plugin startup

## Prerequisites

1. **Stream Deck MCP Server** running at `http://localhost:9090/mcp`
2. **Python 3.x** with `requests` library

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
  "auto_discover": false,
  "timeout": 30
}
```

### 3. Deploy

```batch
setup.bat stream-deck -deploy
```

### 4. Use

In G-Assist, say:
- "Discover Stream Deck tools" → Connects to MCP server and discovers available actions
- "Call Stream Deck tool press_button with button 1" → Executes a specific action

## How It Works

### MCP Protocol Flow

1. **Initialize Session**:
   ```
   POST /mcp
   {"jsonrpc": "2.0", "method": "initialize", ...}
   → Response includes mcp-session-id header
   ```

2. **Discover Tools**:
   ```
   POST /mcp (with mcp-session-id header)
   {"jsonrpc": "2.0", "method": "tools/list", ...}
   → Returns list of available tools
   ```

3. **Call Tool**:
   ```
   POST /mcp (with mcp-session-id header)
   {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "...", "arguments": {...}}}
   → Returns tool result
   ```

### Dynamic Manifest Updates

When tools are discovered, the plugin:
1. Converts MCP tool schemas to G-Assist function definitions
2. Writes updated `manifest.json` to the plugin directory
3. Registers dynamic command handlers for each tool

**Example**: If MCP server has a tool called `press_button`, the manifest gets:
```json
{
  "name": "mcp_press_button",
  "description": "Press a button on Stream Deck",
  "properties": {
    "button_id": {"type": "integer", "description": "Button ID to press"}
  }
}
```

## Commands

| Command | Description |
|---------|-------------|
| `mcp_discover_tools` | Connect to MCP server and discover available tools |
| `mcp_call` | Call any MCP tool by name with JSON arguments |
| `mcp_<tool_name>` | (Dynamic) Direct command for each discovered tool |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `mcp_server_url` | `http://localhost:9090/mcp` | MCP server endpoint |
| `auto_discover` | `false` | Auto-discover tools on plugin startup |
| `timeout` | `30` | Request timeout in seconds |

## Files

```
stream-deck/
├── plugin.py           # Main plugin code
├── manifest.json       # Function definitions (updated dynamically)
├── config.json         # MCP server configuration
├── requirements.txt    # Python dependencies (requests)
└── README.md           # This file
```

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\stream-deck\stream-deck.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Failed to initialize MCP session" | Ensure MCP server is running at the configured URL |
| "No tools discovered" | Check MCP server has tools registered |
| Dynamic tools not appearing | Restart G-Assist after discovery to reload manifest |
| Connection timeout | Increase `timeout` in config.json |

## MCP Server Setup

This plugin expects an MCP server that implements:
- `initialize` - Start a session
- `tools/list` - List available tools
- `tools/call` - Execute a tool

See the [MCP Specification](https://modelcontextprotocol.io/) for details.

## License

Apache License 2.0


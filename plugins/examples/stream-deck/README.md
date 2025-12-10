# Stream Deck Plugin

A G-Assist plugin that integrates with **Elgato Stream Deck** via an MCP (Model Context Protocol) server. This plugin discovers your configured Stream Deck actions and lets you execute them with natural language.

## Features

- **Action Discovery**: Automatically discovers all executable actions configured on your Stream Deck
- **Dynamic Functions**: Each discovered action becomes a callable function
- **Natural Language**: Execute actions by simply asking (e.g., "open the webpage" or "play the audio")
- **Session Management**: Handles MCP session lifecycle automatically

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

In G-Assist:

1. **Discover your Stream Deck**: "Discover my Stream Deck"
2. **Execute actions**: "Open the webpage" or "Play the audio" or "Start the timer"

## How It Works

### Discovery Flow

1. Plugin connects to the Stream Deck MCP server
2. Queries for all executable actions configured on your Stream Deck
3. Creates a function for each action (e.g., `streamdeck_open_webpage`)
4. Updates the manifest with discovered functions
5. You can now execute any action by name

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
| `streamdeck_<action>` | (Dynamic) Execute a discovered action |

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `mcp_server_url` | `http://localhost:9090/mcp` | MCP server endpoint |
| `timeout` | `30` | Request timeout in seconds |

## Files

```
stream-deck/
├── plugin.py           # Main plugin code
├── manifest.json       # Function definitions (updated on discovery)
├── config.json         # MCP server configuration (created on first run)
├── actions_cache.json  # Cached actions (created on discovery)
├── requirements.txt    # Python dependencies
├── libs/               # SDK and dependencies
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

# MCP Stdio Filesystem Plugin — G-Assist Example

A complete example showing how to build a **G-Assist plugin** that wraps the
official **[@modelcontextprotocol/server-filesystem](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem)**
Node.js MCP server, communicating over the **stdio transport** (newline-delimited
JSON-RPC 2.0 piped through stdin/stdout of a subprocess).

No custom MCP server code is required — the plugin spawns a real,
production-quality filesystem server via `npx` and auto-discovers all its tools.

## Architecture

```
┌────────────────────┐  length-prefixed   ┌──────────────────┐
│   G-Assist Engine  │◄══════════════════►│    plugin.py     │
│                    │   JSON-RPC 2.0     │   (MCPPlugin +   │
│                    │   (G-Assist proto) │  StdioTransport) │
└────────────────────┘                    └────────┬─────────┘
                                                   │ stdio (stdin/stdout)
                                                   │ newline-delimited JSON
                                         ┌─────────▼──────────────┐
                                         │ @modelcontextprotocol/  │
                                         │ server-filesystem       │
                                         │ (Node.js, via npx)     │
                                         │ <allowed_dirs...>      │
                                         └────────────────────────┘
```

1. **G-Assist Engine** launches `plugin.py` and communicates over
   length-prefixed JSON-RPC 2.0 (the standard G-Assist plugin protocol).
2. **`plugin.py`** uses `StdioTransport` to spawn
   `npx -y @modelcontextprotocol/server-filesystem <dirs>` as a child process,
   communicating over newline-delimited JSON-RPC 2.0 (the standard MCP stdio
   transport).
3. At startup the plugin **auto-discovers** every tool the server exposes
   and registers them as G-Assist commands.

## Files

| File               | Description                                                  |
|--------------------|--------------------------------------------------------------|
| `plugin.py`        | G-Assist plugin — `MCPPlugin` + `StdioTransport`            |
| `manifest.json`    | Plugin manifest describing available functions               |
| `requirements.txt` | Notes on prerequisites (no pip packages needed)              |
| `libs/`            | SDK folder — copy `gassist_sdk` here (see Setup)            |
| `README.md`        | This file                                                    |

## Discovered Tools

These are auto-discovered from the MCP server at startup:

| Tool                       | Description                                       |
|----------------------------|---------------------------------------------------|
| `read_file`                | Read a file's contents (text)                     |
| `read_text_file`           | Read a text file with encoding support            |
| `read_media_file`          | Read an image/audio file as base64                |
| `read_multiple_files`      | Read several files at once                        |
| `write_file`               | Create or overwrite a file                        |
| `edit_file`                | Line-based find-and-replace edits                 |
| `create_directory`         | Create directories (including nested)             |
| `list_directory`           | List files and directories with `[FILE]`/`[DIR]`  |
| `list_directory_with_sizes`| List files and directories including sizes        |
| `directory_tree`           | Recursive tree view as JSON                       |
| `move_file`                | Move or rename files/directories                  |
| `search_files`             | Glob-pattern search for files                     |
| `get_file_info`            | File/directory metadata (size, dates, perms)      |
| `list_allowed_directories` | Show which directories the server may access      |

Plus one static command added directly in `plugin.py`:

| Command          | Description                                             |
|------------------|---------------------------------------------------------|
| `plugin_status`  | Show plugin info, MCP server details, and allowed dirs  |

## Prerequisites

- **Python 3.9+** (for the plugin itself)
- **Node.js >= 18** (provides `npx`, used to run the MCP filesystem server)

Verify Node.js and npx are available:

```bash
node --version   # should print v18.x or higher
npx --version    # should be available alongside node
```

If not installed, see https://nodejs.org/

> **Note:** No `pip install` is required. The MCP filesystem server is the
> Node.js package `@modelcontextprotocol/server-filesystem` and is fetched
> automatically by `npx` on first run.

## Setup

### 1. Copy the SDK into `libs/`

```bash
cd plugins/examples/mcp-stdio-example
mkdir -p libs
cp -r ../../sdk/python/gassist_sdk libs/
```

### 2. Verify the structure

```
mcp-stdio-example/
├── plugin.py
├── manifest.json
├── requirements.txt
├── README.md
└── libs/
    └── gassist_sdk/
        ├── __init__.py
        ├── plugin.py
        ├── protocol.py
        ├── types.py
        └── mcp.py
```

### 3. (Optional) Set the allowed directories

By default the plugin scopes filesystem access to `~/Documents`. Override
with an environment variable (comma-separated for multiple directories):

```bash
export MCP_FS_ALLOWED_DIRS="/path/to/project,/path/to/another"
```

Or edit the `ALLOWED_DIRS` constant in `plugin.py`.

## How It Works

### 1. Stdio Transport

`StdioTransport` from the SDK spawns the MCP filesystem server as a child
process via `npx` and pipes MCP messages through its stdin/stdout:

```python
from gassist_sdk.mcp import StdioTransport

stdio_transport = StdioTransport(
    command=["npx", "-y", "@modelcontextprotocol/server-filesystem", *ALLOWED_DIRS],
    env={"PYTHONUNBUFFERED": "1"},
)
```

### 2. MCPPlugin with Custom Transport

Pass the transport to `MCPPlugin` instead of a URL:

```python
from gassist_sdk import MCPPlugin

plugin = MCPPlugin(
    name="mcp-stdio-filesystem",
    version="1.0.0",
    mcp_transport=stdio_transport,
)
```

### 3. Auto-Discovery

The `@plugin.discoverer` decorator registers a function called at startup.
It queries the MCP server for its tools and registers each one as a
G-Assist command with full argument forwarding:

```python
@plugin.discoverer
def discover_tools(mcp: MCPClient) -> List[FunctionDef]:
    tools = mcp.list_tools()
    for tool in tools:
        def make_handler(name):
            def handler(**kwargs):
                return mcp.call_tool(name, kwargs)
            return handler

        plugin._commands[sanitize_name(tool["name"])] = CommandInfo(
            name=sanitize_name(tool["name"]),
            handler=make_handler(tool["name"]),
            description=tool.get("description", ""),
        )
    return []
```

### 4. Execution Flow

When a user asks *"List the files in my project"*:

1. The engine matches the query to the `list_directory` function.
2. Sends an `execute` request to `plugin.py`.
3. The plugin calls `mcp.call_tool("list_directory", {"path": "..."})`.
4. `StdioTransport` writes the JSON-RPC request to the server's stdin.
5. `@modelcontextprotocol/server-filesystem` lists the directory and writes
   the result to stdout.
6. The result flows back through the plugin to the engine and the user.

## Testing with the Plugin Emulator

```bash
cd plugins

# Create a test directory with the plugin symlinked
mkdir -p /tmp/test-plugins
ln -sf "$(pwd)/examples/mcp-stdio-example" /tmp/test-plugins/mcp-stdio-example

# Run a command (use --timeout to allow time for npx startup)
MCP_FS_ALLOWED_DIRS=/path/to/allowed/dir \
python3 -m plugin_emulator -d /tmp/test-plugins --timeout 120000 \
  exec list_directory --args '{"path": "/path/to/allowed/dir"}'

# Or run in interactive mode
MCP_FS_ALLOWED_DIRS=/path/to/allowed/dir \
python3 -m plugin_emulator -d /tmp/test-plugins --timeout 120000 interactive
```

## Extending

- **Change the allowed directories** — set `MCP_FS_ALLOWED_DIRS` or edit
  `plugin.py`.
- **Swap in a different MCP server** — any stdio-compatible MCP server
  works.  Just change the `command` list in `StdioTransport`.
- **Enable polling** — set `poll_interval=60` to re-discover tools
  periodically if your MCP server changes dynamically.

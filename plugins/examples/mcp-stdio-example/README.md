# MCP Stdio Filesystem Plugin — G-Assist Example

A complete example showing how to build a **G-Assist plugin** that wraps the
popular open-source **[mcp-server-filesystem](https://github.com/MarcusJellinghaus/mcp_server_filesystem)**
Python package, communicating over the **stdio transport** (newline-delimited
JSON-RPC 2.0 piped through stdin/stdout of a subprocess).

No custom MCP server code is required — the plugin spawns a real,
production-quality filesystem server and auto-discovers all its tools.

## Architecture

```
┌────────────────────┐  length-prefixed   ┌──────────────────┐
│   G-Assist Engine  │◄══════════════════►│    plugin.py     │
│                    │   JSON-RPC 2.0     │   (MCPPlugin +   │
│                    │   (G-Assist proto) │  StdioTransport) │
└────────────────────┘                    └────────┬─────────┘
                                                   │ stdio (stdin/stdout)
                                                   │ newline-delimited JSON
                                         ┌─────────▼──────────┐
                                         │ mcp-server-         │
                                         │ filesystem           │
                                         │ (pip package)        │
                                         │ --project-dir ~/Docs │
                                         └──────────────────────┘
```

1. **G-Assist Engine** launches `plugin.py` and communicates over
   length-prefixed JSON-RPC 2.0 (the standard G-Assist plugin protocol).
2. **`plugin.py`** uses `StdioTransport` to spawn `mcp-server-filesystem`
   as a child process, communicating over newline-delimited JSON-RPC 2.0
   (the standard MCP stdio transport).
3. At startup the plugin **auto-discovers** every tool the server exposes
   (`list_directory`, `read_file`, `save_file`, `edit_file`, …) and
   registers them as G-Assist commands.

## Files

| File               | Description                                                  |
|--------------------|--------------------------------------------------------------|
| `plugin.py`        | G-Assist plugin — `MCPPlugin` + `StdioTransport`            |
| `manifest.json`    | Plugin manifest describing available functions               |
| `requirements.txt` | Python dependency (`mcp-server-filesystem`)                  |
| `libs/`            | SDK folder — copy `gassist_sdk` here (see Setup)            |
| `README.md`        | This file                                                    |

## Discovered Tools

These are auto-discovered from the MCP server at startup:

| Tool               | Description                                           |
|--------------------|-------------------------------------------------------|
| `list_directory`   | List files/dirs, respects `.gitignore`                |
| `read_file`        | Read a file's contents                                |
| `save_file`        | Create or overwrite a file (atomic)                   |
| `append_file`      | Append content to an existing file                    |
| `edit_file`        | Selective find-and-replace edits                      |
| `delete_this_file` | Permanently remove a file                             |
| `move_file`        | Move or rename files/directories                      |

Plus one static command added directly in `plugin.py`:

| Command          | Description                                             |
|------------------|---------------------------------------------------------|
| `plugin_status`  | Show plugin info, MCP server details, and project dir   |

## Setup

### 1. Install the MCP server

```bash
pip install mcp-server-filesystem
```

### 2. Copy the SDK into `libs/`

```bash
cd plugins/examples/mcp-stdio-example
mkdir -p libs
cp -r ../../sdk/python/gassist_sdk libs/
```

### 3. Verify the structure

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

### 4. (Optional) Set the project directory

By default the plugin scopes filesystem access to `~/Documents`.  Override
with an environment variable:

```bash
export MCP_FS_PROJECT_DIR="/path/to/your/project"
```

Or edit the `PROJECT_DIR` constant in `plugin.py`.

## How It Works

### 1. Stdio Transport

`StdioTransport` from the SDK spawns `mcp-server-filesystem` as a child
process and pipes MCP messages through its stdin/stdout:

```python
from gassist_sdk.mcp import StdioTransport

stdio_transport = StdioTransport(
    command=["mcp-server-filesystem", "--project-dir", PROJECT_DIR],
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
It queries the MCP server for its tools and wraps each one as a
`FunctionDef`:

```python
@plugin.discoverer
def discover_tools(mcp: MCPClient) -> List[FunctionDef]:
    tools = mcp.list_tools()     # e.g. list_directory, read_file, …
    functions = []
    for tool in tools:
        def make_executor(name):
            def executor(**kwargs):
                return mcp.call_tool(name, kwargs)
            return executor

        functions.append(FunctionDef(
            name=sanitize_name(tool["name"]),
            description=tool.get("description", ""),
            executor=make_executor(tool["name"]),
        ))
    return functions
```

### 4. Execution Flow

When a user asks *"List the files in my project"*:

1. The engine matches the query to the `list_directory` function.
2. Sends an `execute` request to `plugin.py`.
3. The plugin calls `mcp.call_tool("list_directory", {})`.
4. `StdioTransport` writes the JSON-RPC request to the server's stdin.
5. `mcp-server-filesystem` lists the directory and writes the result to stdout.
6. The result flows back through the plugin to the engine and the user.

## Testing with the Plugin Emulator

```bash
cd ../../plugin_emulator
python engine.py --plugin ../examples/mcp-stdio-example/plugin.py
```

## Extending

- **Change the project directory** — set `MCP_FS_PROJECT_DIR` or edit
  `plugin.py`.
- **Add reference projects** — append `--reference-project name=/path`
  to the server command in `_build_server_command()`.
- **Swap in a different MCP server** — any stdio-compatible MCP server
  works.  Just change the `command` list in `StdioTransport`.
- **Enable polling** — set `poll_interval=60` to re-discover tools
  periodically if your MCP server changes dynamically.

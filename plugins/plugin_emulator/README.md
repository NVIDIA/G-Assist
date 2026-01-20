# G-Assist Plugin Emulator

A Python tool that emulates the engine's plugin communication capabilities for plugin development and testing. It allows plugin developers to test and validate their plugins without needing the full G-Assist engine.

## Features

- **Plugin Manifest Scanning**: Automatically discovers and parses plugin manifests
- **JSON-RPC 2.0 Communication**: Full protocol V2 support with length-prefixed framing
- **Interactive Menu Interface**: User-friendly menu for testing plugins
- **Automatic Passthrough Mode**: Enters passthrough when plugin requests it (`keep_session=true`)
- **Plugin Validation**: Comprehensive compliance scorecard
- **MCP Plugin Support**: Waits for MCP plugins to discover functions after startup
- **File Watcher**: Auto-detects plugin changes and prompts for reload
- **Heartbeat Enforcement**: Monitor plugin liveness with ping/pong
- **Streaming Support**: Real-time output from plugins

## Installation

```bash
# From the plugins/plugin_emulator directory
pip install -r requirements.txt
```

Or install from the `plugins` directory:
```bash
pip install -r plugin_emulator/requirements.txt
```

## Quick Start

### Interactive Mode (Default)

Simply run with the plugins directory - this is the recommended way to use the emulator:

```bash
python -m plugin_emulator -d /path/to/plugins
```

This presents a menu-driven interface:

```
----------------------------------------
MAIN MENU
----------------------------------------
  1. List all plugins
  2. Select a plugin (view functions)
  3. Execute a function
  4. Validate a plugin
  5. Reload plugins
  0. Exit
----------------------------------------
```

### CLI Commands (for scripting)

#### List Plugins

```bash
python -m plugin_emulator -d /path/to/plugins list plugins
```

#### List Functions

```bash
python -m plugin_emulator -d /path/to/plugins list functions
```

#### Execute a Function

```bash
# With JSON arguments
python -m plugin_emulator -d /path/to/plugins exec my_function --args '{"param": "value"}'

# With key=value pairs
python -m plugin_emulator -d /path/to/plugins exec my_function --args "param=value,other=123"
```

#### Passthrough Mode

Enter passthrough mode to have an extended conversation with a plugin:

```bash
python -m plugin_emulator -d /path/to/plugins passthrough my_plugin
```

Type `exit`, `quit`, or `done` to leave passthrough mode.

**Note**: In interactive mode, passthrough is entered automatically when a plugin responds with `keep_session=true`.

### Autonomous Testing

Run automated tests with LLM judge evaluation:

```bash
# Set your NVIDIA API key
export LLM_API_KEY=your_api_key_here

# Run tests from a test file
python -m plugin_emulator -d /path/to/plugins test --test-file tests.json

# Run a single test
python -m plugin_emulator -d /path/to/plugins test \
    --function my_function \
    --prompt "Do something useful" \
    --expectation "Should return a helpful response"
```

## Startup Progress

The emulator shows detailed progress during initialization:

```
Scanning plugins directory: /path/to/plugins
Discovered 5 plugin(s): corsair, gemini, logiled, modio, stream-deck

Loading plugins...
  [1/5] Loading corsair... OK (16 functions)
  [2/5] Loading gemini... OK (1 functions)
  [3/5] Loading logiled... OK (3 functions)
  [4/5] Loading modio... OK (2 functions)
  [5/5] Loading stream-deck... OK (8 functions) (MCP)

Starting 5 persistent plugin(s)...
  [1/5] Starting corsair... OK
  [2/5] Starting gemini... FAILED: Plugin process died
  [3/5] Starting logiled... OK
  [4/5] Starting modio... OK
  [5/5] Starting stream-deck... OK

Waiting for MCP plugins to discover functions: stream-deck
  ..... done

Initialization complete: 5 plugins, 30 functions
```

## Plugin Validation

The emulator includes a comprehensive validation suite. Select option 4 from the main menu to validate a plugin:

- **Manifest compliance** - Required fields, versions, function definitions
- **Startup behavior** - Process starts cleanly, responds to initialize
- **Protocol compliance** - JSON-RPC 2.0 format, proper framing
- **Heartbeat/ping response** - Timely pong responses
- **Function execution** - All functions execute without errors
- **Stress testing** - Rapid consecutive calls
- **Error handling** - Graceful handling of invalid inputs
- **Shutdown behavior** - Clean process termination

Results are displayed as a scorecard and can be exported to JSON.

## File Watcher

The emulator monitors the plugins directory for changes. When a plugin is added, removed, or modified, you'll see:

```
==================================================
  PLUGIN CHANGES DETECTED
==================================================

  + New plugins:
      my-new-plugin

  ~ Updated plugins:
      stream-deck

  Press 5 to reload or continue with current state
==================================================
```

## Test File Format

For autonomous testing, create a JSON file with test definitions:

```json
{
    "tests": [
        {
            "function": "my_function",
            "prompt": "What user would say to trigger this function",
            "expectation": "Description of expected behavior",
            "arguments": {
                "param1": "value1"
            }
        }
    ]
}
```

## Plugin Manifest Format

Plugins must have a `manifest.json` file in their directory:

```json
{
    "manifestVersion": 1,
    "protocol_version": "2.0",
    "description": "My awesome plugin",
    "executable": "plugin.py",
    "persistent": false,
    "passthrough": false,
    "functions": [
        {
            "name": "my_function",
            "description": "Does something useful",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Input parameter"
                    }
                },
                "required": ["input"]
            }
        }
    ],
    "tags": ["utility", "example"]
}
```

### MCP Plugins

For MCP-enabled plugins, add:

```json
{
    "mcp": {
        "enabled": true,
        "launch_on_startup": true
    }
}
```

The emulator will wait 5 seconds after starting MCP plugins to allow them to connect to their MCP server and discover functions.

## Protocol V2 (JSON-RPC 2.0)

The emulator communicates with plugins using JSON-RPC 2.0 with length-prefixed framing:

### Message Format
```
[4-byte big-endian length][UTF-8 JSON payload]
```

### Engine → Plugin Methods

- `initialize` - Initialize the plugin
- `execute` - Execute a function
- `shutdown` - Shutdown the plugin
- `ping` - Check plugin liveness
- `input` - Send user input (passthrough mode)

### Plugin → Engine Notifications

- `stream` - Streaming output data
- `complete` - Command completed (with `keep_session` to request passthrough)
- `error` - Error occurred
- `log` - Log message

## Python API

You can also use the emulator programmatically:

```python
from plugin_emulator import PluginEngine, EngineConfig

# Create engine
config = EngineConfig(plugins_dir="/path/to/plugins")
engine = PluginEngine(config=config)

# Initialize
engine.initialize()

# List plugins
for plugin in engine.list_plugins():
    print(f"Plugin: {plugin.name}")

# Execute a function
result = engine.execute("my_function", {"input": "hello"})
print(f"Success: {result.success}")
print(f"Response: {result.response}")

# Handle passthrough automatically
if result.awaiting_input:
    while engine.is_in_passthrough:
        user_input = input("> ")
        if user_input == "exit":
            engine.exit_passthrough()
            break
        result = engine.send_input(user_input)
        print(result.response)

# Cleanup
engine.shutdown()
```

## Directory Structure

```
plugin_emulator/
├── __init__.py          # Package exports
├── __main__.py          # Entry point for -m plugin_emulator
├── cli.py               # Command-line interface
├── engine.py            # Main PluginEngine class
├── manager.py           # PluginManager for multi-plugin handling
├── plugin.py            # Plugin process management
├── protocol.py          # JSON-RPC 2.0 protocol implementation
├── manifest.py          # Manifest parsing
├── validator.py         # Plugin validation suite
├── watcher.py           # File system watcher
├── requirements.txt     # Dependencies
└── README.md            # This file
```

## Comparison with G-Assist Engine

| Feature | G-Assist Engine (C++) | plugin_emulator (Python) |
|---------|---------------------|------------------------|
| Protocol V2 | ✅ | ✅ |
| Manifest parsing | ✅ | ✅ |
| Process management | ✅ | ✅ |
| Heartbeat/watchdog | ✅ | ✅ |
| Passthrough mode | ✅ | ✅ |
| Streaming output | ✅ | ✅ |
| MCP support | ✅ | ✅ |
| LLM inference | ✅ | ❌ (uses judge instead) |
| Autonomous testing | ❌ | ✅ |
| Plugin validation | ❌ | ✅ |
| Interactive menu | ❌ | ✅ |
| File watcher | ❌ | ✅ |
| Cross-platform | Windows | Windows/Linux/Mac |

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](../examples/hello-world/LICENSE) file for details.

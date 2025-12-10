# Hello World G-Assist Plugin

A simple example plugin demonstrating the **G-Assist SDK** and **JSON-RPC V2 protocol**.

This plugin is intentionally minimal to serve as a starting point for building your own plugins.

## Features Demonstrated

| Feature | Command | Description |
|---------|---------|-------------|
| **Basic Command** | `say_hello` | Simple function that takes a parameter and returns a greeting |
| **Streaming Output** | `count_with_streaming` | Shows how to send partial results using `plugin.stream()` |
| **Passthrough Mode** | `start_conversation` | Multi-turn conversation with `set_keep_session(True)` |
| **Input Handling** | `on_input` | Handles follow-up messages in passthrough mode |

## Quick Start

### 1. Setup

From the `examples/` folder, run:

```batch
setup.bat hello-world
```

This pip installs dependencies from `requirements.txt` and copies the SDK to `libs/`.

### 2. Deploy

Copy this entire folder to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world\
```

The plugin runs directly as a Python script - no build step required!

## Project Structure

```
hello-world/
├── plugin.py        # Main plugin code
├── manifest.json    # Function definitions for LLM
├── config.json      # Plugin configuration
├── libs/            # Dependencies (SDK and any other packages)
│   └── gassist_sdk/ # G-Assist Plugin SDK
├── requirements.txt # Lists pip dependencies to install
└── README.md        # This file

# Shared setup script in parent folder:
examples/
└── setup.bat        # Shared setup script for all plugins
```

## Dependencies

All dependencies are listed in `requirements.txt` and copied to the `libs/` subfolder by `setup.bat`. The engine automatically adds `libs/` to Python's search path when running the plugin.

**To add new dependencies:**
1. Add the package name to `requirements.txt`
2. Run `setup.bat` (for SDK packages) or `pip install <package> --target libs/` (for pip packages)

## How It Works

### The SDK Pattern

```python
from gassist_sdk import Plugin, Context

# 1. Create a plugin instance
plugin = Plugin(
    name="hello-world",
    version="1.0.0",
    description="A simple example plugin"
)

# 2. Register commands using decorators
@plugin.command("say_hello")
def say_hello(name: str = "World"):
    return f"Hello, {name}!"

# 3. Run the plugin
if __name__ == "__main__":
    plugin.run()
```

### Streaming Responses

Send partial results as they become available:

```python
@plugin.command("long_operation")
def long_operation():
    plugin.stream("Starting...\n")
    # do work...
    plugin.stream("50% complete...\n")
    # do more work...
    plugin.stream("Done!")
    return ""  # All output was streamed
```

### Passthrough Mode (Multi-turn Conversations)

Keep the session open for follow-up messages:

```python
@plugin.command("start_chat")
def start_chat(topic: str):
    plugin.set_keep_session(True)  # Enable passthrough
    return f"Let's talk about {topic}!"

@plugin.command("on_input")
def on_input(content: str):
    if content.lower() == "exit":
        plugin.set_keep_session(False)  # Exit passthrough
        return "Goodbye!"
    
    plugin.set_keep_session(True)  # Stay in passthrough
    return f"You said: {content}"
```

## Protocol Details

This plugin uses **Protocol V2** (JSON-RPC 2.0) which the SDK handles automatically:

- ✅ Length-prefixed message framing
- ✅ Automatic ping/pong responses (no heartbeat code needed!)
- ✅ Input acknowledgment
- ✅ Error handling
- ✅ Graceful shutdown

See `sdk/python/PROTOCOL_V2.md` for full protocol documentation.

## Configuration

Edit `config.json` to customize greetings:

```json
{
    "greeting": "Hello",
    "farewell": "Goodbye"
}
```

After deployment, config is stored at:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world\config.json
```

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world\hello-world.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot import gassist_sdk" | Run `setup.bat hello-world` from examples folder |
| Commands not recognized | Ensure `manifest.json` function names match `@plugin.command()` names |
| Plugin not responding | Check the log file for errors |

## License

Apache License 2.0 - See LICENSE file for details.

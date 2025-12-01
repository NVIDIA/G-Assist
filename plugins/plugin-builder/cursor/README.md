# Cursor Rules for G-Assist Plugin Development

Place the `.cursorrules` file from this directory into your Cursor workspace to get AI-assisted guidance for creating new G-Assist plugins.

## How to Use

1. **Copy the rules file** into your Cursor workspace root:
   ```batch
   copy plugins\plugin-builder\cursor\.cursorrules .cursorrules
   ```

2. **Open Cursor** and start a conversation. The AI will:
   - Interview you about your plugin (name, purpose, functions, etc.)
   - Guide you through copying the `hello-world` example
   - Help you customize `plugin.py`, `manifest.json`, and `config.json`
   - Generate plugin-specific `.cursorrules` for future development
   - Remind you to run `setup.bat` to install dependencies

3. **Follow the prompts** - each step includes ready-to-run commands.

## Protocol V2 (JSON-RPC)

All plugins use **Protocol V2** with the G-Assist SDK. The SDK handles:
- Message framing (length-prefixed)
- JSON-RPC 2.0 communication
- Automatic ping/pong responses
- Error handling

You just write your business logic using simple decorators:

```python
from gassist_sdk import Plugin

plugin = Plugin("my-plugin", version="1.0.0")

@plugin.command("my_function")
def my_function(param: str):
    plugin.stream("Working...")
    return "Result"

if __name__ == "__main__":
    plugin.run()
```

## Reference Examples

| Example | Description |
|---------|-------------|
| `plugins/examples/hello-world/` | Simple example - basic commands, streaming, passthrough |
| `plugins/examples/gemini/` | Production plugin - API integration, setup wizard, streaming |

## Setup & Deploy

From the `plugins/examples/` folder:

```batch
setup.bat hello-world              # Install dependencies only
setup.bat hello-world -deploy      # Install and deploy to RISE
setup.bat all -deploy              # Setup and deploy all plugins
```

## Why Keep Rules Here?

This folder is the authoritative source for Cursor automation. When patterns evolve, update the `.cursorrules` here so every developer gets consistent guidance.

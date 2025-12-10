# G-Assist Plugin SDK

A simple Python SDK for building G-Assist plugins.

## Installation

```bash
pip install .
```

Or for development:
```bash
pip install -e .
```

## Quick Start

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

## API Reference

### Plugin Class

```python
Plugin(
    name: str,           # Plugin name (must match manifest.json)
    version: str,        # Plugin version
    description: str,    # Plugin description
    use_legacy_protocol: bool  # Use V1 protocol (for backwards compatibility)
)
```

#### Methods

- `plugin.command(name, description)` - Decorator to register a command
- `plugin.stream(data)` - Send streaming data
- `plugin.log(message, level)` - Send log message
- `plugin.set_keep_session(keep)` - Set passthrough mode
- `plugin.run()` - Start the plugin main loop

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


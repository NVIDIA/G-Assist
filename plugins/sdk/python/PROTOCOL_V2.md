# G-Assist Plugin Protocol (V2)

## Overview

The G-Assist Plugin Protocol is based on **JSON-RPC 2.0** (same as MCP - Model Context Protocol), providing a standardized, well-documented way for plugins to communicate with the G-Assist engine.

**⚠️ IMPORTANT: All plugins MUST use Protocol V2. Legacy V1 protocol is no longer supported.**

## Design Goals

1. **Developer Simplicity**: SDK hides all protocol details
2. **Engine Protection**: Engine-driven ping, immediate freeze detection
3. **Standards-Based**: JSON-RPC 2.0 for interoperability
4. **Robust**: Watchdog thread independently monitors plugin health

## Message Framing

All messages use length-prefix framing:

```
┌──────────────────┬─────────────────────────────┐
│ Length (4 bytes) │ JSON-RPC Message (N bytes)  │
│ Big-endian uint  │ UTF-8 encoded               │
└──────────────────┴─────────────────────────────┘
```

This eliminates the need for delimiter-based parsing and handles binary/special characters safely.

## JSON-RPC 2.0 Format

### Request (Engine → Plugin)
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "methodName",
    "params": { ... }
}
```

### Response (Plugin → Engine)
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": { ... }
}
```

### Error Response
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "error": {
        "code": -32600,
        "message": "Invalid Request",
        "data": { ... }
    }
}
```

### Notification (No response expected)
```json
{
    "jsonrpc": "2.0",
    "method": "methodName",
    "params": { ... }
}
```

## Protocol Methods

### Engine → Plugin

#### `initialize`
Called once when plugin starts.

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocol_version": "2.0",
        "engine_version": "1.0.0",
        "capabilities": ["streaming", "passthrough"]
    }
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "name": "my-plugin",
        "version": "1.0.0",
        "capabilities": ["streaming"]
    }
}
```

#### `ping`
Health check - plugin MUST respond within 1 second.

```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "ping",
    "params": { "timestamp": 1234567890 }
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "result": { "timestamp": 1234567890 }
}
```

**⚠️ CRITICAL: Plugins that miss 2 consecutive pings will be terminated by the engine watchdog.**

#### `execute`
Execute a plugin command/function.

```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "execute",
    "params": {
        "function": "search_web",
        "arguments": { "query": "NVIDIA stock price" },
        "context": [...],
        "system_info": "..."
    }
}
```

Response (non-streaming):
```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
        "success": true,
        "data": "The current NVIDIA stock price is...",
        "keep_session": true
    }
}
```

#### `input`
User input during passthrough mode.

```json
{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "input",
    "params": {
        "content": "Tell me more about that",
        "timestamp": 1234567890
    }
}
```

Plugin MUST first acknowledge:
```json
{
    "jsonrpc": "2.0",
    "id": 4,
    "result": { "acknowledged": true }
}
```

Then send streaming/final response via notifications.

#### `shutdown`
Graceful shutdown request.

```json
{
    "jsonrpc": "2.0",
    "method": "shutdown",
    "params": {}
}
```

No response expected - plugin should exit.

### Plugin → Engine (Notifications)

#### `stream`
Send streaming content during execution.

```json
{
    "jsonrpc": "2.0",
    "method": "stream",
    "params": {
        "request_id": 3,
        "data": "Searching for NVIDIA stock..."
    }
}
```

#### `complete`
Signal execution complete.

```json
{
    "jsonrpc": "2.0",
    "method": "complete",
    "params": {
        "request_id": 3,
        "success": true,
        "data": "Final result here",
        "keep_session": true
    }
}
```

#### `error`
Report an error during execution.

```json
{
    "jsonrpc": "2.0",
    "method": "error",
    "params": {
        "request_id": 3,
        "code": -1,
        "message": "API rate limit exceeded"
    }
}
```

#### `log`
Send log messages for debugging (optional).

```json
{
    "jsonrpc": "2.0",
    "method": "log",
    "params": {
        "level": "info",
        "message": "Processing query..."
    }
}
```

## Timeouts

| Operation | Timeout | Action on Timeout |
|-----------|---------|-------------------|
| ping → pong | 1 second | Kill plugin |
| input → ack | 2 seconds | Kill plugin |
| execute → complete | 30 seconds | Kill plugin |
| Session total | 5 minutes | Kill plugin |

## Error Codes

Standard JSON-RPC 2.0 error codes plus custom:

| Code | Message | Meaning |
|------|---------|---------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid Request | Not valid JSON-RPC |
| -32601 | Method not found | Unknown method |
| -32602 | Invalid params | Invalid parameters |
| -32603 | Internal error | Internal plugin error |
| -1 | Plugin error | Custom plugin error |
| -2 | Timeout | Operation timed out |
| -3 | Rate limited | Too many requests |

## Manifest Requirements

The `manifest.json` file should include the protocol version:

```json
{
    "manifestVersion": 1,
    "name": "my-plugin",
    "version": "1.0.0",
    "protocol_version": "2.0",
    "executable": "./plugin.exe",
    "functions": [...]
}
```

## SDK Usage (Python)

```python
from gassist_sdk import Plugin

plugin = Plugin("my-plugin", version="1.0.0")

@plugin.command("search_web")
def search_web(query: str, context: list = None):
    """Search the web for information."""
    plugin.stream("Searching...")
    results = do_search(query)
    return {"results": results}

@plugin.command("get_weather")  
def get_weather(location: str):
    """Get weather for a location."""
    return get_weather_data(location)

if __name__ == "__main__":
    plugin.run()
```

The SDK handles:
- Message framing (length-prefix)
- JSON-RPC 2.0 protocol
- Ping/pong responses (automatic!)
- Input acknowledgment (automatic)
- Error handling and reporting
- Graceful shutdown

## Migration from V1

If you have an existing V1 plugin, you need to:

1. Install the SDK: `pip install gassist_sdk` (or add SDK path)
2. Replace your plugin code with SDK-based code (see example above)
3. Update `manifest.json` to include `"protocol_version": "2.0"`
4. Remove all heartbeat/threading code - SDK handles this automatically
5. Remove all pipe I/O code - SDK handles this automatically

**The SDK reduces a typical 200+ line plugin to ~20 lines of actual business logic!**

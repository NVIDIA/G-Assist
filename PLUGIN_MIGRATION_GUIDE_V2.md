# G-Assist Plugin Migration Guide: V1 to V2

## Table of Contents

1. [Overview](#overview)
2. [What's Changed](#whats-changed)
3. [Quick Start Migration](#quick-start-migration)
4. [Step-by-Step Migration](#step-by-step-migration)
5. [Protocol V2 Reference](#protocol-v2-reference)
6. [SDK Documentation](#sdk-documentation)
7. [Troubleshooting](#troubleshooting)
8. [Examples](#examples)

---

## Overview

Protocol V2 is a complete overhaul of the G-Assist plugin communication system, bringing:

- **JSON-RPC 2.0 standard** for interoperability
- **Engine-driven health monitoring** (no more plugin heartbeat threads!)
- **Length-prefixed framing** (eliminates delimiter parsing bugs)
- **Independent watchdog thread** for robust failure detection
- **Native Python support** with auto-discovery and PYTHONPATH injection

> ⚠️ **IMPORTANT:** All plugins MUST use Protocol V2. Legacy V1 protocol is no longer supported.

---

## What's Changed

### Protocol Comparison

| Feature | V1 (Legacy) | V2 (Current) |
|---------|-------------|--------------|
| Message Format | Raw JSON + `<<END>>` delimiter | JSON-RPC 2.0 with 4-byte length prefix |
| Framing | String-based delimiter parsing | Binary length-prefixed framing |
| Heartbeat | Plugin-initiated (threading required) | Engine-driven ping/pong (automatic) |
| Watchdog | None | Independent watchdog thread |
| Python Support | Requires compilation to .exe | Direct .py execution |
| SDK Lines Required | ~200+ lines boilerplate | ~20 lines business logic |

### Message Framing

**V1 (Problematic):**
```
{"message": "Hello"}<<END>>
```
- ❌ Fails if plugin output contains `<<END>>`
- ❌ String-based parsing is fragile

**V2 (Robust):**
```
┌──────────────────┬─────────────────────────────┐
│ Length (4 bytes) │ JSON-RPC Message (N bytes)  │
│ Big-endian uint  │ UTF-8 encoded               │
└──────────────────┴─────────────────────────────┘
```
- ✅ Binary length header
- ✅ Handles any content safely

### Heartbeat Changes

**V1:** Plugin must implement heartbeat thread:
```python
# V1 - Plugin had to do this
def heartbeat_loop():
    while running:
        send_response({"type": "heartbeat"})
        time.sleep(5)

threading.Thread(target=heartbeat_loop).start()
```

**V2:** SDK handles it automatically:
```python
# V2 - SDK responds to pings automatically
# No heartbeat code needed in your plugin!
```

---

## Quick Start Migration

### Before (V1 - ~200+ lines):

```python
import sys
import json
import threading
import time

class Plugin:
    def __init__(self):
        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.heartbeat_thread.start()
    
    def _heartbeat_loop(self):
        while self.running:
            self._send_response({"type": "heartbeat"})
            time.sleep(5)
    
    def _send_response(self, data):
        response = json.dumps(data) + "<<END>>"
        sys.stdout.write(response)
        sys.stdout.flush()
    
    def _read_command(self):
        buffer = ""
        while True:
            chunk = sys.stdin.read(1)
            buffer += chunk
            if buffer.endswith("<<END>>"):
                return json.loads(buffer[:-7])
    
    def run(self):
        while self.running:
            try:
                command = self._read_command()
                result = self._handle_command(command)
                self._send_response({"success": True, "message": result})
            except Exception as e:
                self._send_response({"success": False, "message": str(e)})

if __name__ == "__main__":
    plugin = Plugin()
    plugin.run()
```

### After (V2 - ~20 lines):

```python
from gassist_sdk import Plugin

plugin = Plugin("my-plugin", version="1.0.0")

@plugin.command("search_web")
def search_web(query: str):
    """Search the web for information."""
    plugin.stream("Searching...")
    results = do_search(query)
    return {"results": results}

if __name__ == "__main__":
    plugin.run()
```

---

## Step-by-Step Migration

### Step 1: Update manifest.json

Add the protocol version field:

```json
{
  "manifestVersion": 1,
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My awesome plugin",
  "protocol_version": "2.0",
  "executable": "plugin.py",
  "persistent": true,
  "functions": [
    {
      "name": "my_function",
      "description": "Does something useful",
      "tags": ["utility"],
      "properties": {
        "param1": {
          "type": "string",
          "description": "First parameter"
        }
      },
      "required": ["param1"]
    }
  ]
}
```

**Key changes:**
- Add `"protocol_version": "2.0"`
- Executable can now be `.py` directly (no need to compile to `.exe`)

### Step 2: Install the SDK

#### Python

Copy the `gassist_sdk` folder to your plugin's `libs/` directory:

```
my-plugin/
├── plugin.py
├── manifest.json
├── config.json (optional)
├── requirements.txt
└── libs/
    └── gassist_sdk/
        ├── __init__.py
        ├── plugin.py
        ├── protocol.py
        └── types.py
```

The engine automatically adds `libs/` to PYTHONPATH.

#### C++

Include the header-only SDK:

```cpp
#include <nlohmann/json.hpp>
#include "gassist_sdk.hpp"
```

#### Node.js

Copy `gassist-sdk.js` to your plugin directory.

### Step 3: Rewrite Plugin Code

#### Python Example

```python
"""
My Plugin - Migrated to Protocol V2
"""
import os
import sys
import logging

# SDK import (from libs/ folder)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

from gassist_sdk import Plugin, Context

# Configuration
PLUGIN_NAME = "my-plugin"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create plugin instance
plugin = Plugin(
    name=PLUGIN_NAME,
    version="1.0.0",
    description="My migrated plugin"
)

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@plugin.command("my_function")
def my_function(param1: str, param2: int = 0, context: Context = None):
    """
    Description of what this function does.
    
    Args:
        param1: First parameter (required)
        param2: Second parameter (optional, default: 0)
        context: Conversation context (provided by engine)
    
    Returns:
        Result dictionary
    """
    logger.info(f"Executing my_function with param1={param1}, param2={param2}")
    
    # Send streaming output (optional)
    plugin.stream("Processing your request...")
    
    # Do your work here
    result = f"Processed: {param1} with value {param2}"
    
    # Return result (will be sent to user)
    return {"result": result}


@plugin.command("interactive_mode")
def interactive_mode(topic: str = "general"):
    """
    Start an interactive session (passthrough mode).
    
    Args:
        topic: What to discuss
    """
    logger.info(f"Starting interactive mode for topic: {topic}")
    
    # Enter passthrough mode - user input goes to on_input
    plugin.set_keep_session(True)
    
    return f"""🎯 Interactive Mode Started

Topic: {topic}

You can now send messages directly to me.
Type 'exit' to leave interactive mode.

What would you like to discuss?"""


@plugin.command("on_input")
def on_input(content: str):
    """
    Handle user input during passthrough mode.
    
    This is called automatically when:
    1. Plugin previously set keep_session=True
    2. User sends a new message
    
    Args:
        content: The user's message
    """
    content = content.strip()
    logger.info(f"Received input: {content[:50]}...")
    
    # Check for exit commands
    if content.lower() in ["exit", "quit", "bye", "done"]:
        plugin.set_keep_session(False)  # Exit passthrough mode
        return "👋 Goodbye! Exiting interactive mode."
    
    # Process the input
    response = f"You said: {content}"
    
    # Stay in passthrough mode
    plugin.set_keep_session(True)
    
    return response


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin...")
    plugin.run()
```

#### C++ Example

```cpp
#include <nlohmann/json.hpp>
#include "gassist_sdk.hpp"
#include <string>

int main() {
    gassist::Plugin plugin("my-plugin", "1.0.0", "My migrated plugin");
    
    // Register command
    plugin.command("my_function", [&](const nlohmann::json& args) {
        std::string param1 = args.value("param1", "");
        int param2 = args.value("param2", 0);
        
        // Streaming output
        plugin.stream("Processing...");
        
        // Return result
        return nlohmann::json{
            {"result", "Processed: " + param1}
        };
    });
    
    // Interactive mode
    plugin.command("interactive_mode", [&](const nlohmann::json& args) {
        plugin.set_keep_session(true);
        return nlohmann::json("Interactive mode started. Type 'exit' to leave.");
    });
    
    // Handle input in passthrough mode
    plugin.command("on_input", [&](const nlohmann::json& args) {
        std::string content = args.value("content", "");
        
        if (content == "exit") {
            plugin.set_keep_session(false);
            return nlohmann::json("Goodbye!");
        }
        
        plugin.set_keep_session(true);
        return nlohmann::json("You said: " + content);
    });
    
    plugin.run();
    return 0;
}
```

### Step 4: Remove Legacy Code

Delete the following from your plugin:

| Remove | Reason |
|--------|--------|
| Heartbeat thread/loop | SDK handles ping/pong automatically |
| `<<END>>` delimiter handling | SDK uses length-prefix framing |
| Manual stdin/stdout I/O | SDK handles all I/O |
| JSON serialization code | SDK handles serialization |
| Timeout handling | Engine handles timeouts |
| Signal handlers | SDK handles shutdown |

### Step 5: Test Your Plugin

1. **Build/Deploy:**
   - Copy plugin to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<name>\`

2. **Check Logs:**
   - Plugin log: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<name>\<name>.log`
   - SDK log: `gassist_sdk.log` in plugin directory or temp folder
   - Engine log: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\logs\`

3. **Test Commands:**
   - Try each function through G-Assist
   - Test streaming output
   - Test passthrough mode (if applicable)

---

## Protocol V2 Reference

### Message Format

All messages use JSON-RPC 2.0 with length-prefix framing:

```
[4-byte big-endian length][UTF-8 JSON payload]
```

### Engine → Plugin Messages

#### initialize

Called once when plugin starts.

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocol_version": "2.0",
        "engine_version": "1.0.0"
    }
}
```

**Response:**
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "name": "my-plugin",
        "version": "1.0.0",
        "protocol_version": "2.0",
        "commands": [
            {"name": "my_function", "description": "..."}
        ]
    }
}
```

#### ping

Health check - **MUST respond within 1 second**.

```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "ping",
    "params": {"timestamp": 1234567890}
}
```

**Response:**
```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "result": {"timestamp": 1234567890}
}
```

> ⚠️ Plugins that miss 2 consecutive pings will be terminated.

#### execute

Execute a plugin command.

```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "execute",
    "params": {
        "function": "my_function",
        "arguments": {"param1": "value", "param2": 42},
        "context": [...],
        "system_info": "..."
    }
}
```

#### input

User input during passthrough mode.

```json
{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "input",
    "params": {
        "content": "user message here",
        "timestamp": 1234567890
    }
}
```

**Must acknowledge first:**
```json
{
    "jsonrpc": "2.0",
    "id": 4,
    "result": {"acknowledged": true}
}
```

#### shutdown

Graceful shutdown request (no response needed).

```json
{
    "jsonrpc": "2.0",
    "method": "shutdown",
    "params": {}
}
```

### Plugin → Engine Messages (Notifications)

#### stream

Send streaming content during execution.

```json
{
    "jsonrpc": "2.0",
    "method": "stream",
    "params": {
        "request_id": 3,
        "data": "Searching for results..."
    }
}
```

#### complete

Signal execution complete.

```json
{
    "jsonrpc": "2.0",
    "method": "complete",
    "params": {
        "request_id": 3,
        "success": true,
        "data": "Final result here",
        "keep_session": false
    }
}
```

**keep_session:** Set to `true` to stay in passthrough mode.

#### error

Report an error.

```json
{
    "jsonrpc": "2.0",
    "method": "error",
    "params": {
        "request_id": 3,
        "code": -1,
        "message": "Something went wrong"
    }
}
```

#### log

Debug logging (optional).

```json
{
    "jsonrpc": "2.0",
    "method": "log",
    "params": {
        "level": "info",
        "message": "Processing step 1..."
    }
}
```

### Timeouts

| Operation | Timeout | Action on Timeout |
|-----------|---------|-------------------|
| ping → pong | 1 second | Kill plugin |
| input → ack | 2 seconds | Kill plugin |
| execute → complete | 30 seconds | Kill plugin |

### Error Codes

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

---

## SDK Documentation

### Python SDK

#### Installation

Copy `gassist_sdk/` folder to your plugin's `libs/` directory.

#### Basic Usage

```python
from gassist_sdk import Plugin, Context

plugin = Plugin("my-plugin", version="1.0.0")

@plugin.command("function_name")
def function_name(arg1: str, arg2: int = 0, context: Context = None):
    """Function description."""
    return "result"

plugin.run()
```

#### API Reference

**Plugin class:**

| Method | Description |
|--------|-------------|
| `Plugin(name, version, description)` | Create plugin instance |
| `@plugin.command(name, description)` | Register command handler |
| `plugin.stream(data)` | Send streaming output |
| `plugin.set_keep_session(bool)` | Enter/exit passthrough mode |
| `plugin.log(message, level)` | Send log message |
| `plugin.run()` | Start plugin main loop |

**Context class:**

| Property | Description |
|----------|-------------|
| `context.messages` | List of conversation messages |
| `context.last_message` | Most recent message |

#### Passthrough Mode

```python
@plugin.command("start_chat")
def start_chat():
    plugin.set_keep_session(True)  # Enter passthrough
    return "Chat started. Type 'exit' to leave."

@plugin.command("on_input")
def on_input(content: str):
    if content == "exit":
        plugin.set_keep_session(False)  # Exit passthrough
        return "Goodbye!"
    
    plugin.set_keep_session(True)  # Stay in passthrough
    return f"You said: {content}"
```

### C++ SDK

#### Installation

Include the header-only SDK:

```cpp
#include <nlohmann/json.hpp>
#include "gassist_sdk.hpp"
```

#### Basic Usage

```cpp
#include "gassist_sdk.hpp"

int main() {
    gassist::Plugin plugin("my-plugin", "1.0.0");
    
    plugin.command("function_name", [&](const nlohmann::json& args) {
        std::string arg1 = args.value("arg1", "");
        return nlohmann::json{{"result", arg1}};
    });
    
    plugin.run();
    return 0;
}
```

#### API Reference

| Method | Description |
|--------|-------------|
| `Plugin(name, version, description)` | Create plugin instance |
| `command(name, handler)` | Register command handler |
| `stream(data)` | Send streaming output |
| `set_keep_session(bool)` | Enter/exit passthrough mode |
| `run()` | Start plugin main loop |

---

## Troubleshooting

### Plugin Not Starting

**Symptoms:** Plugin doesn't appear, no response

**Check:**

1. **Python availability:**
   - Bundled: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\python\python.exe`
   - Developer: Set `GA_PYTHON_DEV=C:\path\to\python.exe`
   - System: Ensure Python is in PATH

2. **Manifest validity:**
   ```bash
   # Validate JSON syntax
   python -m json.tool manifest.json
   ```

3. **Logs:**
   - Engine: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\logs\`
   - Plugin: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<name>\<name>.log`

### Plugin Timing Out

**Symptoms:** "Plugin not responding" errors

**Causes:**

1. **Not responding to ping:**
   - SDK handles this automatically
   - If using custom code, respond within 1 second

2. **Blocking operations:**
   - Use threading for long operations
   - Send `stream` notifications during processing

3. **Command taking too long:**
   - Default timeout is 30 seconds
   - Break up long operations with streaming

### "Invalid JSON-RPC" Errors

**Check:**

1. All messages include `"jsonrpc": "2.0"`
2. Using length-prefix framing (not `<<END>>`)
3. SDK is properly imported

### Passthrough Mode Not Working

**Check:**

1. `set_keep_session(True)` called before returning
2. `on_input` command registered
3. Not calling `set_keep_session(False)` unexpectedly

### Import Errors (Python)

**Error:** `ModuleNotFoundError: No module named 'gassist_sdk'`

**Fix:**

```python
import os
import sys

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

from gassist_sdk import Plugin
```

---

## Examples

### Simple Function Plugin

```python
from gassist_sdk import Plugin

plugin = Plugin("hello-world", "1.0.0")

@plugin.command("say_hello")
def say_hello(name: str = "World"):
    return f"Hello, {name}! 👋"

if __name__ == "__main__":
    plugin.run()
```

### Streaming Output Plugin

```python
from gassist_sdk import Plugin
import time

plugin = Plugin("counter", "1.0.0")

@plugin.command("count_to")
def count_to(number: int = 5):
    plugin.stream(f"Counting to {number}...\n\n")
    
    for i in range(1, number + 1):
        plugin.stream(f"🔢 {i}\n")
        time.sleep(0.3)
    
    return f"✅ Done counting to {number}!"

if __name__ == "__main__":
    plugin.run()
```

### Interactive Chat Plugin

```python
from gassist_sdk import Plugin

plugin = Plugin("chat", "1.0.0")
chat_history = []

@plugin.command("start_chat")
def start_chat(topic: str = "anything"):
    chat_history.clear()
    plugin.set_keep_session(True)
    return f"💬 Let's chat about {topic}!\n\nType 'exit' to end."

@plugin.command("on_input")
def on_input(content: str):
    if content.lower() in ["exit", "quit", "bye"]:
        plugin.set_keep_session(False)
        return "👋 Goodbye!"
    
    chat_history.append(content)
    plugin.set_keep_session(True)
    return f"Message #{len(chat_history)}: {content}"

if __name__ == "__main__":
    plugin.run()
```

### API Integration Plugin

```python
from gassist_sdk import Plugin
import requests

plugin = Plugin("weather", "1.0.0")

@plugin.command("get_weather")
def get_weather(location: str):
    plugin.stream(f"🔍 Looking up weather for {location}...\n")
    
    try:
        # Your API call here
        response = requests.get(f"https://api.weather.com/{location}")
        data = response.json()
        
        return f"""☀️ Weather for {location}:
Temperature: {data['temp']}°F
Conditions: {data['conditions']}
"""
    except Exception as e:
        return f"❌ Error: {str(e)}"

if __name__ == "__main__":
    plugin.run()
```

---

## Support

For issues or questions:

1. Check the logs (see Troubleshooting section)
2. Verify manifest.json is valid
3. Ensure SDK is properly installed
4. Test with a minimal example first

---

*Document Version: 2.0*
*Last Updated: December 2024*


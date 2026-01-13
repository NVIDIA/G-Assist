---
description: "Guide developers through creating a new G-Assist plugin using the SDK-based Protocol V2."
globs:
alwaysApply: true
---
# G-Assist Plugin Builder - Protocol V2 (JSON-RPC)

## Purpose
Guide developers through creating a new G-Assist plugin using the SDK-based Protocol V2.

## Reference Examples
- **hello-world**: Simple example demonstrating SDK basics (`plugins/examples/hello-world/`)
- **gemini**: Production plugin with streaming, passthrough, and setup wizard (`plugins/examples/gemini/`)
- **SDK Documentation**: `plugins/sdk/python/README.md` and `plugins/sdk/python/PROTOCOL_V2.md`

## Interview Steps
When a developer opens this folder, guide them through:

1. **Gather Requirements**
    - Plugin name (lowercase, hyphenated, e.g., `my-plugin`)
    - One-line description of what it does
    - Target APIs/services or hardware it interacts with
    - Functions to expose:
    * Function name (snake_case)
    * Parameters (name, type, description, required?)
    * Description for the LLM to understand when to call it
    * Tags for discoverability
    - Does it need a setup wizard? (API keys, authentication, etc.)
    - Does it need passthrough mode? (multi-turn conversations)
    - Should it be persistent? (long-running background process)

2. **Confirm Summary**
    Echo back a structured summary and confirm accuracy before proceeding.

3. **Create Plugin Structure**
    Copy `plugins/examples/hello-world/` to `plugins/examples/<plugin_name>/` and update:

    **plugin.py**:
    ```python
    from gassist_sdk import Plugin, Context

    plugin = Plugin(
        name="<plugin-name>",
        version="1.0.0",
        description="<description>"
    )

    @plugin.command("<function_name>")
    def function_name(param: str, context: Context = None):
        """Function description."""
        plugin.stream("Processing...")  # For streaming output
        result = do_something(param)
        return result

    @plugin.command("on_input")
    def on_input(content: str):
        """Handle follow-up input in passthrough mode."""
        if content.lower() in ["exit", "quit"]:
            plugin.set_keep_session(False)
            return "Goodbye!"
        plugin.set_keep_session(True)
        return f"You said: {content}"

    if __name__ == "__main__":
        plugin.run()
    ```

    **manifest.json**:
    ```json
    {
    "manifestVersion": 1,
    "name": "<plugin-name>",
    "version": "1.0.0",
    "description": "<description>",
    "executable": "plugin.py",
    "persistent": true,
    "protocol_version": "2.0",
    "functions": [
        {
        "name": "<function_name>",
        "description": "<LLM-facing description>",
        "tags": ["<tag1>", "<tag2>"],
        "properties": {
            "<param>": {
            "type": "string",
            "description": "<param description>"
            }
        },
        "required": ["<param>"]
        }
    ]
    }
    ```

    **requirements.txt**: List pip dependencies (SDK is copied separately)

    **config.json**: Plugin-specific configuration

4. **Setup & Deploy Instructions**
    ```batch
    cd plugins\examples
    setup.bat <plugin-name>           # Install dependencies to libs/
    setup.bat <plugin-name> -deploy   # Install and deploy to RISE
    ```

    Validate JSON: `python -m json.tool manifest.json`

## SDK Key Patterns

### Basic Command
```python
@plugin.command("function_name")
def function_name(param: str):
    return "Result"
```

### Streaming Output
```python
@plugin.command("long_operation")
def long_operation():
    plugin.stream("Starting...")
    # do work
    plugin.stream("Done!")
    return ""  # All output was streamed
```

### Passthrough Mode (Multi-turn Conversations)
```python
@plugin.command("start_chat")
def start_chat():
    plugin.set_keep_session(True)  # Enable passthrough
    return "Chat started! Type 'exit' to leave."

@plugin.command("on_input")
def on_input(content: str):
    if content.lower() == "exit":
        plugin.set_keep_session(False)  # Exit passthrough
        return "Goodbye!"
    plugin.set_keep_session(True)  # Stay in passthrough
    return f"You said: {content}"
```

### Setup Wizard Pattern
```python
def is_configured():
    return os.path.exists(API_KEY_FILE) and load_api_key()

@plugin.command("main_function")
def main_function(query: str):
    if not is_configured():
        return run_setup_wizard()
    # Normal operation
    return process(query)

@plugin.command("on_input")
def on_input(content: str):
    if not is_configured():
        # User completed setup, verify
        if verify_setup():
            plugin.set_keep_session(False)
            return "Setup complete!"
        plugin.set_keep_session(True)
        return run_setup_wizard()
    # Normal passthrough handling
    ...
```

## Critical Rules

1. **SDK Handles Protocol**: Never implement heartbeat, ping/pong, or message framing - the SDK does this automatically.

2. **Manifest-Code Sync**: Every function in `manifest.json` must have a matching `@plugin.command()` handler. `on_input` is for passthrough and doesn't go in manifest.

3. **Logging Path**: Always log to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<plugin>\<plugin>.log`

4. **Config Path**: Store config at `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<plugin>\config.json`

5. **Dependencies**: All dependencies go in `libs/` folder. Run `setup.bat <plugin>` to install.

6. **No stdout**: Never print to stdout - use `plugin.stream()` for output, `plugin.log()` for debugging.

7. **Python Version**: Ensure dependencies are installed with same Python version as RISE embedded Python.


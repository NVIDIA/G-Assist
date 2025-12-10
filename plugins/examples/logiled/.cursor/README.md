# G-Assist Plugin Builder Assistant

AI-powered guidance for creating G-Assist plugins with zero boilerplate.

## What Is This?

This folder contains a **Cursor Project Rule** in `.mdc` format that provides AI-guided plugin creation:

- **MDC Format** - Markdown with frontmatter supporting metadata (`alwaysApply: true`)
- **Project Rule** - Lives in `.cursor/rules/` directory, version-controlled with your code
- **Always Applied** - Automatically included in every Agent chat session for this project

The assistant acts as an **interactive wizard** that guides you through plugin creation without you having to explain the G-Assist SDK context every time.

## What These Rules Do

The plugin builder rules create an **interactive wizard** that:

1. **Interviews you** - Asks about plugin name, functions, parameters, API keys needed, etc.
2. **Generates code** - Creates `plugin.py`, `manifest.json`, and config files from templates
3. **Validates structure** - Ensures manifest functions match code decorators
4. **Provides setup commands** - Ready-to-run `setup.bat` commands for deployment
5. **Creates documentation** - Generates plugin-specific docs for the new plugin folder

**Key patterns automated:**
- SDK-based Protocol V2 (JSON-RPC) boilerplate
- Streaming output with `plugin.stream()`
- Passthrough mode for multi-turn conversations
- Setup wizards for API keys/authentication
- Standard logging and config paths

## How to Use

### Option 1: Copy to Your Project (Recommended)

Copy the rule file to your project's `.cursor/rules/` directory:

```batch
# Create .cursor/rules directory if it doesn't exist
mkdir .cursor\rules

# Copy the plugin builder rule
copy plugins\plugin-builder\cursor\custom-gassist-plugin-builder-assistant.mdc .cursor\rules\
```

Once copied, the rule **automatically applies to all Agent chats** in your project.

### Option 2: Work Directly in This Folder

Open this folder in Cursor IDE and start chatting - the rule is already active here.

### Using the Assistant

Start a conversation with the Agent (Ctrl+L / Cmd+L) and it will:
- Interview you about your plugin (name, purpose, functions, etc.)
- Guide you through copying the `hello-world` example
- Help you customize `plugin.py`, `manifest.json`, and `config.json`
- Generate plugin-specific documentation
- Remind you to run `setup.bat` to install dependencies

Follow the prompts - each step includes ready-to-run commands.

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

## Files in This Directory

| File | Purpose |
|------|---------|
| `custom-gassist-plugin-builder-assistant.mdc` | Project Rule in MDC format - place in `.cursor/rules/` |
| `README.md` | This documentation |

**Note:** This directory (`plugins/plugin-builder/cursor/`) serves as the template source. Copy the `.mdc` file to your project's `.cursor/rules/` directory to activate it.

## Why Use Cursor Project Rules?

Using Cursor's Project Rules system provides powerful benefits:

1. **Always Available** - With `alwaysApply: true`, the assistant is active in every Agent chat
2. **Version Controlled** - Rules live in `.cursor/rules/` alongside your code
3. **Team Consistency** - Every developer gets identical, up-to-date guidance
4. **Zero Repetition** - No need to re-explain G-Assist SDK patterns in every chat
5. **Persistent Context** - The AI remembers your project's conventions automatically

When SDK patterns evolve, update the `.mdc` file and commit it - all team members instantly benefit.

**Alternatives:**
- **`AGENTS.md`** - Simple markdown file in project root (no metadata, easier for basic use)
- **`.cursorrules`** - Legacy format in project root (still supported but deprecated)

See [Cursor Rules docs](https://cursor.com/docs/context/rules) for details on all formats.

## Additional Resources

- **[Cursor Rules Documentation](https://cursor.com/docs/context/rules)** - Official guide to Project Rules, AGENTS.md, and rule types
- **[Cursor Directory](https://cursor.directory/rules/developer-content)** - Community examples for creating custom rules
- **G-Assist SDK Examples** - `plugins/examples/hello-world/` and `plugins/examples/gemini/`
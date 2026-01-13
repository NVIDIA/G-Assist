# G-Assist Plugin Builder

Transform your ideas into functional G-Assist plugins with AI-powered guidance. This directory contains a **Cursor Project Rule** that acts as an interactive wizard, guiding you through plugin creation step-by-step with zero boilerplate.

## What Can It Do?

- **Interview you** - Asks about plugin name, functions, parameters, API keys needed
- **Generate code** - Creates `plugin.py`, `manifest.json`, and config files from templates
- **Validate structure** - Ensures manifest functions match code decorators
- **Provide setup commands** - Ready-to-run commands for deployment
- **Automate SDK patterns** - Protocol V2 (JSON-RPC), streaming, passthrough mode, setup wizards

## Getting Started with Cursor

### Prerequisites

- [Cursor IDE](https://cursor.com/) installed
- G-Assist installed on your system
- Basic understanding of plugin requirements

### Step 1: Clone the Repository

Clone the full g-assist-plugins-page repository to get the SDK, example plugins, and setup scripts:

```bash
git clone https://github.com/NVIDIA/g-assist-plugins-page.git
cd g-assist-plugins-page
```

### Step 2: Open in Cursor

Open the `plugins/plugin-builder` directory in Cursor IDE:

```bash
cd plugins/plugin-builder
cursor .
```

The Cursor Project Rule (`.cursor/rules/RULE.md`) is automatically active in this directory with `alwaysApply: true`.

### Step 3: Start Building

1. Open the Agent panel (`Ctrl+L` / `Cmd+L`)
2. Describe your plugin idea, for example:
   - "I want to create a weather plugin that can fetch current weather for any city"
   - "I need a plugin that controls my Philips Hue lights"
3. The AI assistant will:
   - Interview you about requirements (name, functions, parameters, etc.)
   - Guide you through copying the `hello-world` example
   - Help you customize `plugin.py`, `manifest.json`, and `config.json`
   - Generate plugin-specific documentation

Follow the prompts - each step includes ready-to-run commands.

## How It Works

The Cursor rule creates an interactive wizard that automates:

- **SDK-based Protocol V2** - JSON-RPC boilerplate handled automatically
- **Streaming output** - Use `plugin.stream()` for real-time responses
- **Passthrough mode** - Multi-turn conversations with `plugin.set_keep_session()`
- **Setup wizards** - API key and authentication flows
- **Standard logging** - Consistent log paths and config locations

### Reference Examples

| Example | Description |
|---------|-------------|
| `plugins/examples/hello-world/` | Simple example - basic commands, streaming, passthrough |
| `plugins/examples/gemini/` | Production plugin - API integration, setup wizard, streaming |

### Documentation

- [`PLUGIN_MIGRATION_GUIDE_V2.md`](../../PLUGIN_MIGRATION_GUIDE_V2.md) - Complete Protocol V2 reference, SDK docs, and migration guide
- `plugins/sdk/python/README.md` - SDK usage guide
- `plugins/sdk/python/PROTOCOL_V2.md` - Protocol specification

## Build and Deploy

From the `plugins/examples/` directory, use `setup.bat`:

```batch
setup.bat <plugin-name>           # Install dependencies to libs/
setup.bat <plugin-name> -deploy   # Install and deploy to RISE
setup.bat all -deploy             # Setup and deploy all plugins
```

Validate your manifest:
```batch
python -m json.tool manifest.json
```

## Example Use Cases

You can create plugins for:
- Weather information
- Task management
- Calendar integration
- Smart home control (lights, switches, sensors)
- Custom data fetching (stocks, APIs)
- Gaming peripherals (RGB lighting, macros)

## Alternative: GPT Plugin Builder

If you prefer not to use Cursor, you can use the OpenAI Custom GPT:

![Plugin Builder GIF](./plugin-builder.gif)

1. Access the [G-Assist Plugin Builder GPT](https://chatgpt.com/g/g-67bcb083cc0c8191b7ca74993785baad-g-assist-plugin-builder)
2. Describe your plugin's purpose and functionality
3. The GPT will generate:
   - Main plugin code
   - Manifest file
   - Configuration file (if needed)
   - Installation instructions

**Tip**: After generation, ask the GPT to "Make sure the files follow the G-Assist Plugin template specifications" to catch inconsistencies.

## Troubleshooting Tips

- **Plugin not loading?** Ensure `manifest.json` functions match `@plugin.command()` decorators in code
- **Build errors?** Run `setup.bat <plugin-name>` to install dependencies to `libs/`
- **No output?** Never use `print()` - use `plugin.stream()` for output, logs for debugging
- **Passthrough not working?** Make sure you have an `on_input` handler and call `plugin.set_keep_session(True)`

### Logging

Add logging to debug issues:

```python
import logging
import os

LOG_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), 
                       "NVIDIA Corporation", "nvtopps", "rise", "plugins", "your-plugin")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "your-plugin.log")
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format="%(asctime)s - %(levelname)s - %(message)s")
```

## Want to Contribute?

We welcome contributions to improve the Plugin Builder! Whether it's:
- Adding new templates
- Improving the Cursor rules
- Enhancing documentation
- Fixing bugs

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Special thanks to:
- Cursor Project Rules
- OpenAI Custom GPTs

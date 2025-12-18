# G-Assist Plugin Builder

Transform your ideas into functional G-Assist plugins with minimal coding! This tool uses AI assistants to generate plugin code, making it easier than ever to extend G-Assist's capabilities. Whether you want to create a weather plugin, a task manager, or any other custom functionality, the Plugin Builder streamlines the entire development process.

> ⚠️ **Protocol V2**: All generated plugins use Protocol V2 with the G-Assist SDK. See the [Plugin Migration Guide](../../PLUGIN_MIGRATION_GUIDE_V2.md) for details.

## What Can It Do?
- Generate complete Protocol V2 plugin code using AI
- Create plugins using the `gassist_sdk` with ~20 lines instead of 200+ boilerplate
- Native Python support - no compilation to `.exe` required
- Works with streaming output, passthrough mode, and setup wizards
- Minimal manual coding required

## Choose Your AI Assistant

| Tool | Best For |
|------|----------|
| **[Cursor Rules](#cursor-ide-plugin-builder)** | Developers using Cursor IDE - interactive wizard with project context |
| **[OpenAI Custom GPT](#openai-custom-gpt)** | Quick generation via ChatGPT web interface |

## Before You Start
Make sure you have:
- G-Assist installed on your system
- Basic understanding of plugin requirements
- For Cursor: [Cursor IDE](https://cursor.com) installed
- For GPT: An OpenAI account with access to [Project G-Assist Custom GPT](https://chatgpt.com/g/g-67bcb083cc0c8191b7ca74993785baad-g-assist-plugin-builder)

💡 **Tip**: Familiarize yourself with G-Assist's plugin architecture and Protocol V2 before starting!

## Getting Started

---

## Cursor IDE Plugin Builder

The recommended way to build plugins if you're using [Cursor IDE](https://cursor.com). The Cursor Rules provide an **interactive wizard** that guides you through plugin creation with full project context.

### Setup Cursor Rules

Copy the rule file to your project's `.cursor/rules/` directory:

```batch
# Create .cursor/rules directory if it doesn't exist
mkdir .cursor\rules

# Copy the plugin builder rule
copy plugins\plugin-builder\cursor\rules\RULE.md .cursor\rules\
```

### Using the Cursor Assistant

1. Open your project in Cursor IDE
2. Start a conversation with the Agent (`Ctrl+L` / `Cmd+L`)
3. The assistant will **interview you** about your plugin:
   - Plugin name and purpose
   - Functions and parameters needed
   - API keys or configuration required
4. It generates Protocol V2-compliant files:
   - `plugin.py` using `gassist_sdk`
   - `manifest.json` with `protocol_version: "2.0"`
   - `config.json` (if needed)
   - Setup and deployment commands

**Key features automated:**
- SDK-based Protocol V2 (JSON-RPC) boilerplate
- Streaming output with `plugin.stream()`
- Passthrough mode for multi-turn conversations
- Setup wizards for API keys/authentication

See the [Cursor Rules README](./cursor/README.md) for detailed documentation.

---

## OpenAI Custom GPT

Use the ChatGPT web interface for quick plugin generation without IDE setup.

### GPT Plugin Builder
![Plugin Builder GIF](./plugin-builder.gif)

### Step 1: Generate Your Plugin
1. Access the [OpenAI Custom GPT](https://chatgpt.com/g/g-67bcb083cc0c8191b7ca74993785baad-g-assist-plugin-builder) for plugin generation
2. Start by clearly describing your plugin's purpose and functionality. For example:
   - "I want to create a weather plugin that can fetch current weather for any city"
   - "I need a plugin that can manage a todo list with voice commands"
3. The GPT will guide you through the process and generate:
   - Main plugin code using `gassist_sdk`
   - Manifest file with `protocol_version: "2.0"`
   - Configuration file (if needed)
   - Installation instructions

💡 **Tip**: For best results, after the files are generated, ask the GPT to "Make sure the files follow Protocol V2 and use the gassist_sdk". This helps catch and correct any potential inconsistencies.

### Step 2: Review and Customize
1. Examine the generated code:
   - Verify `from gassist_sdk import Plugin` import is present
   - Ensure all `@plugin.command()` decorators match manifest functions
   - Review any configuration parameters
   - Check that `plugin.run()` is called in `__main__`

2. Make necessary adjustments:
   - Add error handling where needed
   - Customize response messages
   - Add streaming output with `plugin.stream()`
   - Update any hardcoded values

3. Test the plugin functionality:
   - Test each command individually
   - Verify error cases are handled gracefully
   - Check that responses are formatted correctly
   - Ensure the plugin integrates properly with G-Assist

💡 **Tip**: Use the SDK's built-in logging. Example:
```python
from gassist_sdk import Plugin
import logging
import os

PLUGIN_NAME = "your-plugin"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

plugin = Plugin(PLUGIN_NAME, version="1.0.0")
```

💡 **Tip**: Keep the `manifest.json` functions in sync with `@plugin.command()` decorators in `plugin.py`.

### Step 3: Deploy the Plugin

With Protocol V2, Python plugins run directly - **no compilation required**!

1. Create a new folder in the G-Assist plugins directory:
   ```
   %programdata%\NVIDIA Corporation\nvtopps\rise\plugins\your-plugin-name
   ```

2. Copy your plugin files to this directory:
   ```
   your-plugin-name/
   ├── plugin.py          # Main plugin code
   ├── manifest.json      # Must include "protocol_version": "2.0"
   ├── config.json        # Optional configuration
   └── libs/
       └── gassist_sdk/   # G-Assist SDK
   ```

3. Or use the setup script from `plugins/examples/`:
   ```batch
   setup.bat your-plugin-name -deploy
   ```

💡 **Tip**: The `executable` field in `manifest.json` can now be `plugin.py` directly - no `.exe` needed!

## Example Use Cases
You can create plugins for:
- Weather information
- Task management
- Calendar integration
- Smart home control
- Custom data fetching

💡 **Tip**: Start with a simple plugin to understand the workflow before tackling more complex projects!

## Troubleshooting Tips
- **Generation issues?** Make sure your plugin description is clear and specific
- **Import errors?** Ensure `gassist_sdk/` folder is in your plugin's `libs/` directory
- **Plugin not responding?** Check that `manifest.json` includes `"protocol_version": "2.0"`
- **Plugin not working?** Double-check the deployment folder structure and logs in `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\your-plugin\`

## Want to Contribute?
We welcome contributions to improve the Plugin Builder! Whether it's:
- Adding new templates
- Improving code generation
- Enhancing documentation
- Fixing bugs

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Need Help?
If you run into any issues:
1. Check the troubleshooting section above
2. Review the [Plugin Migration Guide](../../PLUGIN_MIGRATION_GUIDE_V2.md) for Protocol V2 details
3. Review the generated code for any obvious issues
4. Verify your G-Assist installation
5. Check plugin logs in `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<name>\`

## Acknowledgments
Special thanks to:
- OpenAI for their Custom GPT technology
- Cursor for their AI-powered IDE and Project Rules system
- All contributors who help improve this tool
# Project G-Assist Plugins

Project G-Assist is an experimental on-device AI Assistant that helps RTX users control a broad range of PC settings, from optimizing game and system settings, charting frame rates and other key performance statistics, to controlling select peripheral lighting — all via basic voice or text commands.

Project G-Assist is built for community expansion. Whether you're a Python developer, C++ enthusiast, or just getting started — its Plugin architecture makes it easy to define new commands for G-Assist to execute. We can't wait to see what the community dreams up!

## Why Plugins Matter

- Leverage a responsive Small Language Model (SLM) running locally on your own RTX GPU
- Extend and customize G-Assist with functionality that enhances your PC experience
- Interact with G-Assist from the NVIDIA Overlay without needing to tab out or switch programs
- Invoke AI-powered GPU and system controls in your applications using C++ and python bindings
- Integrate with agentic frameworks using tools like Langflow to embed G-Assist in bigger AI pipelines

## What Can You Build?

- Python plugins for rapid development
- C++ plugins for performance-critical applications
- AI-driven features using the [ChatGPT-powered Plugin Builder](./plugins/plugin-builder/)
- Custom system interactions for hardware and OS automation
- Game and application integrations that enhance PC performance or add new commands

If you're looking for inspiration, check out our sample plugins for controlling peripheral & smart home lighting, invoking larger AI models like Gemini, managing Spotify tracks, checking stock prices, getting weather information, or even checking streamers' online status on Twitch — and then let your own ideas take G-Assist to the next level!

## Quick Start 

### Python Development with G-Assist
Get started quickly using our Python bindings of the [C++ APIs](https://github.com/NVIDIA/nvapi/blob/main/nvapi.h#L25283):

1. **Install the binding locally**
```bash
cd api/bindings/python
pip install .
```

2. **Chat with G-Assist**
```python
from rise import rise

# Initialize G-Assist connection
rise.register_rise_client()

# Send and receive messages
response = rise.send_rise_command("What is my GPU?")
print(f'Response: {response}')
"""
Response: Your GPU is an NVIDIA GeForce RTX 5090 with a Driver version of 572.83.
"""
```
3. **Extend G-Assist**


> 💡 **Requirements**:
> - Python 3.x
> - G-Assist core services installed
> - pip package manager

See our [Python Bindings Guide](./api/bindings/python/README.md) for detailed examples and advanced usage.

### NVIDIA Plugin Example - Twitch

Try these commands:
- "Hey Twitch, is Ninja live?"
- "Check if shroud is streaming"
- "Is pokimane online right now?"

### Example Responses

When a streamer is live:
```text
ninja is LIVE!
Title: Friday Fortnite!
Game: Fortnite
Viewers: 45,231
Started At: 2024-03-14T12:34:56Z
```

When a streamer is offline:
```text
ninja is OFFLINE
```

#### Key Features
- Secure API credential management
- OAuth token handling
- Comprehensive logging system
- Windows pipe communication
- Real-time stream status checking

#### Project Structure
```
plugins/examples/twitch/
├── manifest.json        # Plugin configuration
├── config.json          # Twitch API credentials
├── plugin.py            # Main plugin code
├── requirements.txt     # Python dependencies
├── setup.bat            # Environment setup script
└── build.bat            # Build script
```
See our [Twitch Plugin Example Code](./plugins/examples/twitch/) for a step-by-step guide to creating a Twitch integration plugin for G-Assist.


## Table of Contents
- [Project G-Assist Plugins](#-project-g-assist-plugins)
- [Why Plugins Matter](#-why-plugins-matter)
- [What Can You Build?](#-what-can-you-build)
- [Quick Start](#-quick-start)
  - [Python Development with G-Assist](#-python-development-with-g-assist)
  - [NVIDIA Plugin Example - Twitch](#-nvidia-plugin-example---twitch)
- [G-Assist Module Architecture](#-g-assist-module-architecture)
- [Extending G-Assist (Plugins)](#-extending-g-assist-plugins)
  - [What Can You Build?](#-what-can-you-build-1)
  - [Plugin Architecture](#-plugin-architecture)
  - [Plugin Integration](#plugin-integration)
- [NVIDIA-Built G-Assist Plugins](#-nvidia-built-g-assist-plugins)
- [Community-Built Plugins](#-community-built-plugins)
- [Development Tools](#-development-tools)
- [Need Help?](#-need-help)
- [License](#-license)
- [Contributing](#-contributing)

## G-Assist Module Architecture

```mermaid
flowchart TD
    A[System Assist Module]
    A -->|Runs Inference| B[Inference Engine]
    A -->|Implements Built In Functions| C[Core Functions]
    A -->|Launches| D[Plugin Launcher]
    D --> E[Plugin 1]
    D --> F[Plugin 2]
    D --> G[Plugin n]
    H[Community Code]
    H -->|Develops & Contributes| D
```

## Extending G-Assist (Plugins)

Transform your ideas into powerful G-Assist plugins! Whether you're a Python developer, C++ enthusiast, or just getting started, our plugin system makes it easy to extend G-Assist's capabilities. Create custom commands, automate tasks, or build entirely new features - the possibilities are endless!

### Plugin Architecture

Each plugin lives in its own directory named after the plugin (this name is used to invoke the plugin):

```text
plugins/
└── myplugin/              # Plugin directory name = invocation name
    ├── g-assist-plugin-myplugin.exe  # Executable
    ├── manifest.json       # Plugin configuration
    └── config.json         # Settings & credentials (optional)
```

**File Descriptions:**
- `g-assist-plugin-<plugin-name>.exe` - Executable file that executes plugin functionality
- `manifest.json` - Plugin manifest that defines:
    - `name` - plugin identifier
    - `description` - brief description of plugin functionality
    - `executable` - name of the executable file
    - `persistent` - [true/false] whether plugin runs throughout G-Assist lifecycle
    - `functions` - array of available functions with:
      - `name` - function identifier
      - `description` - what the function does
      - `tags` - keywords for AI model to match user intent
      - `properties` - parameters the function accepts
- `config.json` - Configuration file for plugin-specific settings (API keys, credentials, etc.) ⚠️ **Add to `.gitignore`**

> 💡 **Tip**: The plugin directory name is what users will type to invoke your plugin (e.g., "Hey myplugin, do something")

### Plugin Integration
#### How to Call a Plugin from G-Assist

The manifest file acts as the bridge between G-Assist and your plugin. G-Assist automatically scans the plugin directory to discover available plugins.

#### Two Ways to Invoke Plugins:

1. **Natural Language Commands**
    ```
    What are the top upcoming games for 2025?
    ```
    The AI model automatically:
    - Analyzes the user's intent
    - Selects the most appropriate plugin
    - Chooses the relevant function to execute
    - Passes any required parameters

2. **Direct Plugin Invocation**
    ```
    Hey Logitech, change my keyboard lights to green
    ```
    - User explicitly specifies the plugin by name
    - AI model determines the appropriate function from the manifest
    - Parameters are extracted from the natural language command

> 💡 **Pro Tip**: Direct plugin invocation is faster when you know exactly which plugin you need!

## NVIDIA-Built G-Assist Plugins
Explore our official example plugins:

### AI & Information
- **[Gemini AI Integration](./plugins/examples/gemini)** - Query Google's Gemini AI for real-time information, general knowledge, and web searches
- **[Weather](./plugins/examples/weather)** - Get current weather conditions for any city
- **[Stock Market](./plugins/examples/stock)** - Check stock prices and look up ticker symbols
- **[Twitch](./plugins/examples/twitch)** - Check if streamers are live and get stream details

### Smart Lighting
- **[Corsair iCUE](./plugins/examples/corsair)** - Control Corsair RGB peripheral lighting (keyboard, mouse, headset)
- **[Logitech G HUB](./plugins/examples/logiled)** - Control Logitech G RGB peripheral lighting (keyboard, mouse, headset)
- **[Nanoleaf](./plugins/examples/nanoleaf)** - Control Nanoleaf smart lighting panels
- **[OpenRGB](./plugins/examples/openrgb)** - Universal RGB lighting control for multiple device brands

### Automation & Entertainment
- **[Spotify](./plugins/examples/spotify)** - Control Spotify playback, manage playlists, and get track information
- **[IFTTT](./plugins/examples/ifttt)** - Trigger IFTTT applets and automate smart home routines
- **[Discord](./plugins/examples/discord)** - Send messages, charts, screenshots, and clips to Discord channels

## Community-Built Plugins
Check out what others have built:
- [Your Plugin Here] - Submit your plugin using a pull request! We welcome contributions that:
  - Follow our [contribution guidelines](CONTRIBUTING.md)
  - Include proper documentation and examples
  - Have been tested thoroughly
  - Add unique value to the ecosystem

## Development Tools
- **[Python Bindings](./api/bindings/python/)** - Python API for interacting with G-Assist
- **[C++ API](./api/c++/)** - Native C++ interface for performance-critical applications
- **[ChatGPT-powered Plugin Builder](./plugins/plugin-builder/)** - AI-assisted plugin development tool
- **[Plugin Templates](./plugins/templates/)** - Starter templates for Python and C++ plugins

## Need Help?
- Report issues on [GitHub](https://github.com/nvidia/g-assist)

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing
We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

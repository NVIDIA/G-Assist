# 🚀 G-Assist System Assistant

Transform your ideas into powerful AI-enabled applications with G-Assist! This NVIDIA system lets you build applications that leverage local AI models running directly on your GPU. Whether you're creating game integrations, system automation tools, or AI-powered applications, G-Assist provides the foundation you need.

## 💡 Why G-Assist?

Build powerful AI-enabled applications with G-Assist:

- **Local AI Power** 🧠
  - Run SLMs directly on your GPU
  - Get fast, reliable responses
  - Maintain data privacy

- **Flexible Development** 🛠️
  - Use Python or C++ bindings
  - Access GPU and system optimization APIs
  - Build with modern AI frameworks like Langflow

- **Plugin Ecosystem** 🔌
  - Create custom plugins easily
  - Extend G-Assist's core functionality
  - Share with the community

- **Gaming Integration** 🎮
  - Access G-Assist and G-Assist Plugins through NVIDA App's In-Game Overlay
  - Control your GPU and system configuration while gaming
  - Create immersive experiences

Get started quickly with our comprehensive tools and examples!

## 🚀 Quick Start

### 🐍 Python Development with G-Assist
Get started quickly using our Python bindings of the [C++ APIs](https://github.com/NVIDIA/nvapi/blob/main/nvapi.h#L25283):

1. **Install the binding locally**
```bash
cd plugins/bindings/python-bindings
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

See our [Python Bindings Guide](./api/bindings/python) for detailed examples and advanced usage.

See our [C++ Sample Application](./api/c++/sample-app) to create a testing environment for G-Assist's chat capabilities and demonstrates core functionality.

### Extending G-Assist (Plugins)
### 🤖 NVIDIA Plugin Example - Twitch

Try these commands:
- 🗣️ "Hey Twitch, is Ninja live?"
- 🎯 "Check if shroud is streaming"
- 🎮 "Is pokimane online right now?"

### 📝 Example Responses

When a streamer is live:
```text
ninja is LIVE!
Title: Friday Fortnite!
Game: Fortnite
Viewers: 45,231
Started At: 2024-03-14T12:34:56Z
```

When a streamer is offline:
```
ninja is OFFLINE
```

#### ✨ Key Features
- 🔑 Secure API credential management
- 🔄 OAuth token handling
- 📝 Comprehensive logging system
- 🔌 Windows pipe communication
- ⚡ Real-time stream status checking

#### 📁 Project Structure
```
plugins/twitch/
├── manifest.json        # Plugin configuration
├── config.json          # Twitch API credentials
├── plugin.py            # Main plugin code
└── requirements.txt     # Dependencies (requests)
```
See our [Twitch Plugin Example Code](./plugins/examples/twitch/) for a step-by-step guide to creating a Twitch integration plugin for G-Assist.


## 📋 Table of Contents
- [Why G-Assist?](#-why-g-assist)
- [Quick Start](#-quick-start)
  - [🐍 Python Development with G-Assist](#-python-development-with-g-assist)
  - [Extending G-Assist (Plugins)](#extending-g-assist-plugins)
    - [🤖 Twitch Plugin Example](#-nvidia-plugin-example---twitch)
- [System Architecture](#-g-assist-module-architecture)
- [Extending G-Assist](#-extending-g-assist-plugins)
  - [✨ What Can You Build?](#-what-can-you-build)
  - [📦 Plugin Architecture](#-plugin-architecture)
  - [Plugin Integration](#plugin-integration)
- [NVIDIA-Built Plugins](#-nvidia-built-g-assist-plugins)
- [Community-Built Plugins](#-community-built-plugins)
- [Development Tools](#-development-tools)
- [Need Help?](#-need-help)
- [License](#-license)
- [Contributing](#-contributing)

## 📐 G-Assist Module Architecture

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

## 🔌 Extending G-Assist (Plugins)

Transform your ideas into powerful G-Assist plugins! Whether you're a Python developer, C++ enthusiast, or just getting started, our plugin system makes it easy to extend G-Assist's capabilities. Create custom commands, automate tasks, or build entirely new features - the possibilities are endless!

## ✨ What Can You Build?
- 🐍 Python plugins for rapid development
- ⚡ C++ plugins for performance-critical applications
- 🤖 AI-powered plugins using our ChatGPT assisted plugin builder
- 🔌 Custom system interactions
- 🎮 Game and application integrations

### 📦 Plugin Architecture

Each plugin lives in its own directory named after the plugin (this name is used to invoke the plugin):

```text
plugins/
└── myplugin/              # Plugin directory name = invocation name
    ├── g-assist-plugin-my-plugin.exe  # Executable
    ├── manifest.json       # Plugin configuration
    └── config.json         # Settings & credentials
```

- `g-assist-plugin-<plugin-name>.exe` - Executable file that executes plugin functionality
- `manifest.json` - Manifest file that contains: 
    - name of the plugin
    - plugin description
    - list of functions and their parameters, with descriptions for each
    - `tags` - array of keywords used to describe the plugin's functionality
    - `persistent` [true, false] - if the plugin should remain running throughout the entire G-Assist lifecycle 
- `config.json` - Config file containing any required information for the plugin (API key, usernames, other specifications) (⚠️ add to `.gitignore`)

> 💡 **Tip**: The plugin directory name is what users will type to invoke your plugin (e.g., "Hey myplugin, do something")

### Plugin Integration
#### How to Call a Plugin from G-Assist

The manifest file acts as the bridge between G-Assist and your plugin. G-Assist automatically scans the plugin directory to discover available plugins.

#### 🎯 Two Ways to Invoke Plugins:

1. 🤖 Zero-Shot Function Calling
    ```
    /fc What are the top upcoming games for 2025?
    ```
    The AI model automatically:
    - Analyzes the user's intent
    - Selects the most appropriate plugin
    - Chooses the relevant function to execute
    - Passes any required parameters

2. 📢 Direct Plugin Invocation
    ```
    Hey logiled, change my keyboard lights to green
    ```
    or
    ```
    /logiled change my keyboard lights to green
    ```
    - User explicitly specifies the plugin
    - AI model determines the appropriate function from the manifest
    - Parameters are extracted from the natural language command

> 💡 **Pro Tip**: Direct plugin invocation is faster when you know exactly which plugin you need!

## 📚 NVIDIA-Built G-Assist Plugins
Explore our official plugins:
- 🤖 [Gemini AI Integration](./Plugins\Examples\Gemini)
- 🎮 [Logitech Peripheral Lighting](./Plugins\Examples\LogiLED)
- 🎥 [Corsair Peripheral Lighting](./Plugins\Examples\Corsair)
- 💡 [Nanoleaf Room Lighting](./Plugins\Examples\Nanoleaf)
- 📺 [Twitch Integration](./Plugins/Examples/Twitch)
- 🎵 [Spotify Music Player](./Plugins/Examples/Spotify)
- [More coming soon!]

## 🌟 Community-Built Plugins
Check out what others have built:
- [Your Plugin Here] - Submit your plugin using a pull request! We welcome contributions that:
  - Follow our [contribution guidelines](CONTRIBUTING.md)
  - Include proper documentation and examples
  - Have been tested thoroughly
  - Add unique value to the ecosystem

## 🛠️ Development Tools
- 🐍 [Python Bindings](./api/bindings/python/)
- [C++ Sample Application](./api/c++/sample-app/)

## 🆘 Need Help?
- 🐛 Report issues on [GitHub](https://github.com/nvidia/g-assist)

## 📄 License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing
We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.
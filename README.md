# 🚀 G-Assist System Assist Plugins

Transform your ideas into powerful G-Assist plugins! Whether you're a Python developer, C++ enthusiast, or just getting started, our plugin system makes it easy to extend G-Assist's capabilities. Create custom commands, automate tasks, or build entirely new features - the possibilities are endless!

## ✨ What Can You Build?
- 🐍 Python plugins for rapid development
- ⚡ C++ plugins for performance-critical applications
- 🤖 AI-powered plugins using our ChatGPT integration
- 🔌 Custom UI elements and system interactions
- 🎮 Game and application integrations

## 🚀 Quick Start

### Hello World Plugin
Use our python bindings
[need tutorial]

`pip install -r requirements`

## System Assist Module Architecture

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

### APIs to Access G-Assist System Assist
#### Register to Receive G-Assist System Assist Updates
 Informs G-Assist of a client's presence by registering a callback to the client processes. Registration also triggers models and adapters downloads for later use.
``` C++
NVAPI_INTERFACE NvAPI_RegisterRiseCallback(__in NV_RISE_CALLBACK_SETTINGS* pCallbackSettings)
```
#### Send G-Assist System Assist Requests
G-Assist clients send requests to G-Assist to run inference on their behalf

``` C++
NVAPI_INTERFACE NvAPI_RequestRise(__in NV_REQUEST_RISE_SETTINGS* requestContent)
```

To help, we've created a python binding to jumpstart your development. 
```
cd plugins\bindings\python-bindings
```
## Extending System Assistant (Plugins)
### Technical Details
#### Plugin Architecture
- `plugin-name.exe` - Executable file that executes plugin functionality
- `manifest.json` - Manifest file that contains: 
    - name of the plugin
    - plugin description
    - list of functions and their parameters, with descriptions for each
    - `tags` - array of keywords used to describe the plugin's functionality
    - `persistent` [true, false] - if the plugin should remain running throughout the entire G-Assist lifecycle 
- `config.json` - Config file containing and required information for the plugin (API key, usernames, other specifications)

#### 🔌 Plugin Integration
### How to Call a Plugin from G-Assist

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

## 📚 NVIDIA-Built System Assist Plugins
Explore our official plugins:
- 🤖 Gemini AI Integration
- 🎮 Logitech Peripheral Lighting
- 🎥 Corsair Peripheral Lighting
- 💡 Nanoleaf Room Lighting 
- 🎵 Spotify Music Player
- [More coming soon!]

### NVIDIA Plugin Example - Gemini
- Built with Python

#### How to write `initialize` function 
#### Streaming responses
#### Connecting to Gemini with API Key 

## 🌟 Community-Built Plugins
Check out what others have built:
- [Submit your plugin here!]

## 📋 Example Projects
Learn by example with our sample plugins:

## 🛠️ Development Tools
- 🐍 Python Bindings Documentation
- 📗 Node.js Bindings Documentation

## 🆘 Need Help?
- 📖 Check our [Documentation](link-to-docs)
- 💬 Join our [Community Forum](link-to-forum)
- 🐛 Report issues on [GitHub](link-to-github)

## 📄 License
This project is licensed under the [License Name] - see the [LICENSE](LICENSE) file for details.

## 🙏 Contributing
We love contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to help improve G-Assist plugins.
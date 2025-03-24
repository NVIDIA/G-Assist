# 🎮 G-Assist NvTOPPS Sample Application

Transform your applications with NVIDIA G-Assist functionality! This sample app demonstrates how to integrate G-Assist's powerful chat capabilities into your own projects using NvTOPPS.

## ✨ What Can It Do?
- 🤖 Implement G-Assist's chat capabilities in your applications
- 🔄 Receive real-time G-Assist updates through callbacks
- 🚀 Run AI inference directly through G-Assist
- 💻 Test G-Assist functionality in a complete working environment
- 🔧 Easy to configure and customize

## 📋 Before You Start
Make sure you have:
- Windows 10/11
- NVIDIA GPU (RTX 30 series or newer recommended)
- NVIDIA driver 572.83 or newer
- Visual Studio 2019+ (for building from source)
- CMake 3.15+ (for building from source)

💡 **Tip**: Check your NVIDIA driver version in NVIDIA App under "Drivers" page

## 🔧 Required Components

The required NVIDIA API and JSON library are included as submodules in this repository.

1. **Clone with Submodules**
```bash
# Option 1: Clone with submodules in one command
git clone --recurse-submodules <repository-url>

# Option 2: If you already cloned the repository
git submodule init
git submodule update
```

If you downloaded the repository as a ZIP file, you'll need to manually download these dependencies:
- NVIDIA NVAPI files from [NVIDIA GitHub](https://github.com/NVIDIA/nvapi.git)
- JSON library from [nlohmann/json](https://github.com/nlohmann/json.git)

All required files should end up in the [gassist_sample_app](./gassist_sample_app) directory.

## 🚀 Building from Source

1. Clone or download this repository
2. Open `gassist_sample_app.sln` in Visual Studio
3. Configure your build:
   ```
   - Check file locations
   - Select Debug/Release configuration
   - Match platform target to your system
   ```
4. Hit Build! (F7 or Build → Build Solution)

## 🎮 How to Use

### First Time Setup
1. Install NVIDIA driver (572.83+)
2. Launch `gassist_sample_app.exe`
3. Wait for automatic G-Assist component installation
4. Let initialization complete

### Using the Chat Interface
1. Watch for successful G-Assist backend connection
2. Type your message in the chat interface
3. Press Enter to send
4. Wait for AI response

💡 **Tip**: The app will automatically check and install any missing G-Assist components on first launch

## 🔍 Troubleshooting Tips
- **App won't start?**
  - Check your driver version
  - Verify all files are present
  - Ensure GPU is G-Assist-compatible
- **Chat not responding?**
  - Check internet connection
  - Verify G-Assist services are running
  - Try restarting the app

## 🔌 Key APIs

### [Register for G-Assist Updates](https://github.com/NVIDIA/nvapi/blob/main/nvapi.h#L25283)
```C++
NVAPI_INTERFACE NvAPI_RegisterRiseCallback(__in NV_RISE_CALLBACK_SETTINGS* pCallbackSettings)
```

### [Send G-Assist Requests](https://github.com/NVIDIA/nvapi/blob/main/nvapi.h#L25344)
```C++
NVAPI_INTERFACE NvAPI_RequestRise(__in NV_REQUEST_RISE_SETTINGS* requestContent)
```

## 🆘 Need Help?
- Review G-Assist documentation
- Report issues on [GitHub](https://github.com/nvidia/g-assist)

## 📄 License
[Apache 2.0 License](./LICENSE)

## 🛠️ Development Notes
- Built using NVIDIA NVAPI SDK
- Implements NvTOPPS for G-Assist communication
- Uses nlohmann/json for JSON parsing
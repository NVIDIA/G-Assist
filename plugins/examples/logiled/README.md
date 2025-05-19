# Logitech G Illumination Plugin for G-Assist

Transform your Logitech G devices into an interactive lighting experience with G-Assist! This plugin lets you control your Logitech RGB lighting using simple voice commands or the G-Assist interface. Whether you're gaming or working, controlling your Logitech lighting has never been easier.

## What Can It Do?
- Change your Logitech device colors with voice or text commands
- Use natural language: speak or type your commands
- Works with devices supporting the Logitech LED Illumination SDK
- Seamlessly integrates with your G-Assist setup
- Easy to set up and configure

## Before You Start
Make sure you have:
- Windows PC
- Logitech G HUB Gaming Software installed
- Compatible Logitech G devices
- G-Assist installed on your system
- Visual Studio 2022

💡 **Tip**: Not all Logitech devices are supported. Check your device compatibility with LED Illumination SDK 9.00!

## Installation Guide

### Step 1: Get the Files
```bash
git clone --recurse-submodules <repository-url>
cd logiled
```
This downloads all the necessary files to your computer.

### Step 2: Get Required Dependencies
1. Download and install [Logitech G HUB](https://www.logitechg.com/en-us/innovation/g-hub.html)
2. Download [LED Illumination SDK 9.00](https://www.logitechg.com/sdk/LED_SDK_9.00.zip) from the [Developer Lab](https://www.logitechg.com/en-us/innovation/developer-lab.html)
3. Download [JSON for Modern C++ v3.11.3](https://github.com/nlohmann/json/releases/download/v3.11.3/include.zip)

💡 **Tip**: Make sure to install G HUB before proceeding with the build!

### Step 3: Set Up Dependencies
```bash
# Extract the SDK
tar -xf path\to\LED_SDK_9.00.zip

# Extract JSON library
mkdir json && tar -xf path\to\include.zip -C json
```

### Step 4: Build It
1. Open the solution in Visual Studio 2022
2. Select your build configuration (Debug/Release)
3. Build the solution (F7 or Build → Build Solution)

### Step 5: Install the Plugin
1. Create this folder (if it doesn't exist):
   ```
   %programdata%\NVIDIA Corporation\nvtopps\rise\adapters\logiled
   ```
   💡 **Tip**: Copy and paste this path directly into File Explorer's address bar!

2. Copy these files to the folder you just created:
   - `g-assist-plugin-logiled.exe` (from your build output folder)
   - `manifest.json` (from project root)

## How to Use
Once everything is set up, you can control your Logitech devices through G-Assist! Try these commands:
- "Hey logiled, Set my mouse to red"
- "/fc Change my Logitech keyboard to rainbow"
- "/logiled set all devices to blue"

💡 **Tip**: You can use either voice commands or type your requests directly into G-Assist!

## Troubleshooting Tips
- **Build failing?** Make sure all dependencies are extracted to the correct locations
- **Commands not working?** Verify G HUB is running
- **Device not responding?** Check if your device is supported by LED SDK 9.00
- **Plugin not loading?** Double-check the installation folder path

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

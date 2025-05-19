# Corsair Illumination Plugin for G-Assist

Transform your Corsair devices into an interactive lighting experience with G-Assist! This plugin lets you control your Corsair RGB lighting using simple voice commands or the G-Assist interface. Whether you're gaming or working, controlling your Corsair lighting has never been easier.

## What Can It Do?
- Control Corsair device RGB lighting with voice or text commands
- Sync lighting effects across multiple devices
- Works with devices supporting iCUE SDK v4.0.84
- Seamlessly integrates with your G-Assist setup
- Easy to set up and configure

## Before You Start
Make sure you have:
- Windows PC
- Corsair iCUE Software installed
- Compatible Corsair devices
- G-Assist installed on your system
- Visual Studio 2022

💡 **Tip**: Not all Corsair devices are supported. Check your device compatibility with iCUE SDK v4.0.84!

## Installation Guide

### Step 1: Get the Files
```bash
git clone --recurse-submodules <repository-url>
cd corsair
```
This downloads all the necessary files to your computer.

### Step 2: Get Required Dependencies
1. Download [Corsair iCUE Software](https://www.corsair.com/us/en/s/downloads)
2. Download [iCUE SDK v4.0.84](https://github.com/CorsairOfficial/cue-sdk/releases/download/v4.0.84/iCUESDK_4.0.84.zip)
3. Download [JSON for Modern C++ v3.11.3](https://github.com/nlohmann/json/releases/download/v3.11.3/include.zip)

💡 **Tip**: Make sure to install iCUE Software before proceeding with the build!

### Step 3: Set Up Dependencies
```bash
# Extract the SDK
tar -xf path\to\iCUESDK_4.0.84.zip

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
   %programdata%\NVIDIA Corporation\nvtopps\rise\adapters\corsair
   ```
   💡 **Tip**: Copy and paste this path directly into File Explorer's address bar!

2. Copy these files to the folder you just created:
   - `g-assist-plugin-corsair.exe` (from your build output folder)
   - `manifest.json` (from project root)

## How to Use
Once everything is set up, you can control your Corsair devices through G-Assist! Try these commands:
- "Hey Corsair, set my keyboard to red"
- "/fc Change my Corsair lights to rainbow"
- "/corsair set all devices to blue"

💡 **Tip**: You can use either voice commands or type your requests directly into G-Assist!

## Troubleshooting Tips
- **Build failing?** Make sure all dependencies are extracted to the correct locations
- **Commands not working?** Verify iCUE Software is running
- **Device not responding?** Check if your device is supported by iCUE SDK v4.0.84
- **Plugin not loading?** Double-check the installation folder path

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

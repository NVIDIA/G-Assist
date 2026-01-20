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
- Visual Studio 2022 (for building from source)

💡 **Tip**: Not all Logitech devices are supported. Check your device compatibility with LED Illumination SDK 9.00!

✅ **Protocol V2**: This plugin uses **Protocol V2** (JSON-RPC 2.0) with the G-Assist C++ SDK for simplified, standards-based communication!

## Installation Guide

### Quick Installation (Recommended)

The easiest way to install this plugin is using the automated installer:

1. **Build the installer executable:**
   ```bash
   build_installer.bat
   ```
   This creates `plugin-installer.exe` in the current directory.

2. **Run the installer as Administrator:**
   - Right-click `plugin-installer.exe`
   - Select "Run as administrator"
   - Follow the prompts

The installer will:
- ✅ Build the C++ plugin using Visual Studio
- ✅ Install it to the correct NVIDIA G-Assist directory
- ✅ Apply security restrictions to prevent unauthorized modifications
- ✅ Handle all file copying automatically

💡 **Note**: For pre-built plugins, use `build_copy_installer.bat` to create a lightweight installer.

### Manual Installation (Advanced)

If you prefer to build and install manually:

#### Step 1: Setup
From the `plugins/examples` directory, run:
```bash
setup.bat logiled
```
This copies the C++ SDK header to `libs/include/`.

#### Step 2: Get Required Dependencies
1. Download and install [Logitech G HUB](https://www.logitechg.com/en-us/innovation/g-hub.html)
2. Download [LED Illumination SDK 9.00](https://www.logitechg.com/sdk/LED_SDK_9.00.zip) from the [Developer Lab](https://www.logitechg.com/en-us/innovation/developer-lab.html)

**Note:** nlohmann/json is included in the project - no separate download needed.

#### Step 3: Set Up LED SDK
```bash
# Extract the SDK to project directory
tar -xf path\to\LED_SDK_9.00.zip
```

#### Step 4: Build the Plugin
1. Open `logiled.sln` in Visual Studio 2022
2. Select Release configuration and x64 platform
3. Build the solution (F7 or Build → Build Solution)

#### Step 5: Deploy
Deploy using the setup script:
```bash
setup.bat logiled -deploy
```

Or manually copy these files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\logiled`:
- `x64\Release\g-assist-plugin-logiled.exe`
- `manifest.json`

#### Step 6: Test with Plugin Emulator
Test your deployed plugin using the emulator:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the logiled plugin from the interactive menu to test the commands.

⚠️ **Important**: For full security, use the installer which applies ACL restrictions.

## How to Use
Once everything is set up, you can control your Logitech devices through G-Assist! Try these commands:
- "Hey Logitech, set my mouse to red"
- "Change my Logitech keyboard to blue"
- "Set my Logitech headset to green"

💡 **Tip**: You can use either voice commands or type your requests directly into G-Assist!

## Troubleshooting
| Issue | Solution |
|-------|----------|
| Installer failing? | Make sure Visual Studio 2022 is installed with C++ development tools |
| Build failing? | Ensure LED SDK is extracted to the correct location |
| Commands not working? | Verify G HUB is running and "Game lighting control" is enabled in Settings |
| Lighting not changing? | On Windows 11, go to Settings > Personalization > Dynamic Lighting and disable "Use Dynamic Lighting on my devices" |
| Device not responding? | Check if your device is supported by LED SDK 9.00 |
| Plugin not loading? | Check the installation directory and ensure G-Assist is restarted |
| Security errors during install? | Run the installer as Administrator |

## Advanced Configuration

The plugin supports optional configuration through `config.json` in the installation directory:

```json
{
  "features": {
    "use_setup_wizard": false,
    "setup_complete": true,
    "restore_on_shutdown": true,
    "allow_keyboard": true,
    "allow_mouse": true,
    "allow_headset": true
  }
}
```

- `restore_on_shutdown`: Restores original lighting when G-Assist closes
- `allow_keyboard/mouse/headset`: Enable/disable control for specific device types

## Security Features

This plugin implements enhanced security features:
- **ACL Permissions**: Plugin files are protected with restricted access control lists
- **Read-Only for Users**: Regular users can only read/execute, not modify plugin files
- **Admin-Only Modifications**: Only administrators can update the plugin files
- **Automatic Cleanup**: Failed security setups automatically remove insecure files

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

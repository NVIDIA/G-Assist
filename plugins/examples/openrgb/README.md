# OpenRGB G-Assist Plugin

Control your RGB lighting through G-Assist using OpenRGB! This plugin allows you to manage your RGB devices using natural language commands.

## Disclaimer
Please note that by using OpenRGB, you agree to OpenRGB's terms and conditions. OpenRGB is an open-source project that provides direct hardware access to RGB devices.
For more information, see the [OpenRGB GitLab Repository](https://gitlab.com/CalcProgrammer1/OpenRGB) or the [OpenRGB Website](https://openrgb.org/).

## Features
- List all connected RGB devices
- Enable/disable lighting
- Set colors for individual or all devices
- Set different lighting modes/effects
- Support for various color formats

## Requirements
- Python 3.8 or higher
- NVIDIA G-Assist installed on your system
- OpenRGB app running on your system (default port: 6742)

## Installation Guide

### Step 1: Setup
From the `plugins/examples` directory, run:
```bash
setup.bat openrgb
```
This installs all required Python packages (`openrgb-python`) and copies the SDK to `libs/`.

### Step 2: Deploy
Deploy using the setup script:
```bash
setup.bat openrgb -deploy
```

Or manually copy the following files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\openrgb`:
- `plugin.py`
- `manifest.json`
- `libs/` folder (contains dependencies and SDK)

### Step 3: Test with Plugin Emulator
Test your deployed plugin using the emulator:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the openrgb plugin from the interactive menu to test the commands.

## How to Use
Once everything is set up, you can control your RGB devices through G-Assist! Try these commands:
- "Hey OpenRGB, list my devices"
- "Set all my RGB lights to blue"
- "Turn off all lighting"
- "Set my keyboard to rainbow mode"

💡 **Tip**: Make sure OpenRGB is running on your system with SDK server enabled (default port: 6742)!

## Available Commands
- **list_devices**: Returns a list of all connected RGB devices
- **disable_lighting**: Turns off lighting for all devices
- **set_color**: Sets the color for either a specific device or all devices
  - Parameters: `color_name` (required), `device_name` (optional)
- **set_mode**: Sets a specific lighting mode/effect for a device
  - Parameters: `effect_name` (required), `device_name` (optional)

## Troubleshooting
| Issue | Solution |
|-------|----------|
| "OpenRGB service is not running" | Start OpenRGB and enable SDK Server (SDK Server tab) |
| Connection timeout | Check that OpenRGB is running on port 6742 |
| Device not found | Verify device name matches exactly as shown in OpenRGB |
| Color not working | Use supported colors: red, green, blue, yellow, purple, orange, pink, white, black, cyan, magenta |

## OpenRGB Documentation
This plugin uses the OpenRGB Python SDK to control your RGB devices. For more information about OpenRGB and its capabilities, visit:
- [OpenRGB Documentation](https://openrgb.org/)
- [OpenRGB Python SDK](https://github.com/jath03/openrgb-python)

## Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\openrgb\openrgb-plugin.log
```

## Developer Documentation

### Architecture Overview
The OpenRGB plugin is built using the G-Assist SDK (Protocol V2). It uses the `@plugin.command` decorator pattern to register commands and communicates with OpenRGB via the `openrgb-python` library.

### Core Components

#### Plugin Setup
```python
from gassist_sdk import Plugin

plugin = Plugin(
    name="openrgb",
    version="2.0.0",
    description="Control RGB lighting via OpenRGB"
)
```

#### Command Registration
Commands are registered using the `@plugin.command()` decorator:
```python
@plugin.command("list_devices")
def list_devices():
    """List all available RGB devices."""
    if not ensure_connected():
        return "OpenRGB service is not running..."
    
    devices = [device.name for device in CLI.devices]
    return "Available devices:\n" + "\n".join(f"  - {d}" for d in devices)
```

### Color Support
The plugin supports the following predefined colors:
```python
COLOR_MAP = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'purple': (128, 0, 128),
    'orange': (255, 165, 0),
    'pink': (255, 192, 203),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    'cyan': (0, 255, 255),
    'magenta': (255, 0, 255),
}
```

### OpenRGB Integration
- Uses `OpenRGBClient` for device communication
- Default connection: localhost:6742
- Client name: "G-Assist Plugin"
- Supports device discovery and management
- Handles device-specific modes and effects

### Adding New Commands
To add a new command:

1. Add a new function with the `@plugin.command()` decorator:
```python
@plugin.command("new_command")
def new_command(param: str = ""):
    """Command description."""
    if not ensure_connected():
        return "OpenRGB service is not running."
    
    try:
        # Your implementation here
        return "Success message"
    except Exception as e:
        return f"Failed: {e}"
```

2. Add the function to `manifest.json`:
```json
{
    "name": "new_command",
    "description": "Description of the new feature",
    "tags": ["openrgb", "lighting"],
    "properties": {
        "param": {
            "type": "string",
            "description": "Description of the parameter"
        }
    }
}
```

3. Deploy the plugin:
```bash
setup.bat openrgb -deploy
```

4. Test using the plugin emulator:
```bash
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```

5. Test with G-Assist by using voice or text commands to trigger your new function.

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

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
- Python 3.12 or higher
- NVIDIA G-Assist installed on your system
- OpenRGB app running on your system (default port: 6742)

## Installation Guide

### Step 1: Get the Files
```bash
git clone <repository-url>
cd openrgb
```

### Step 2: Set Up Python Environment
```bash
.\setup.bat
```

### Step 3: Build the Plugin
```bash
.\build.bat
```

### Step 4: Run the Plugin
Copy the dist/openrgb folder to the proper directory: `%programdata%\NVIDIA Corporation\nvtopps\rise\plugins`

## Available Commands
- `list_devices`

    Returns a list of all connected RGB devices.

- `disable_lighting`

    Turns off lighting for all devices.

- `set_lighting_to_color`

    Sets the color for either a specific device or all devices.
    Parameters:
    - `color`: Color value (hex, RGB, etc.)
    - `device_name` (optional): Specific device to set color for

- `set_color`

    Sets a specific color for a device by ID.
    Parameters:
    - `device_id`: Numeric ID of the device
    - `color_name`: Color value to set

- `set_mode`

    Sets a specific lighting mode/effect for a device.
    Parameters:
    - `device_id`: Numeric ID of the device
    - `effect_name`: Name of the effect to set

## OpenRGB Documentation
This plugin uses the OpenRGB Python SDK to control your RGB devices. For more information about OpenRGB and its capabilities, visit:
- [OpenRGB Documentation](https://openrgb.org/)
- [OpenRGB Python SDK](https://github.com/jath03/openrgb-python)

## Logging
The plugin logs to `%USERPROFILE%\openrgb_plugin.log` in your user's profile directory, tracking:
- Plugin startup and shutdown
- Command reception and processing
- Error conditions
- Function execution details

## Developer Documentation

### Architecture Overview
The OpenRGB plugin is implemented as a Python-based service that integrates with the OpenRGB SDK to control RGB lighting on various devices through the OpenRGB server.

### Core Components

#### Communication Protocol
- Uses Windows named pipes for IPC
- JSON-based message format
- Command/response structure with success/failure indicators
- End-of-message marker (`<<END>>`)

#### Command Structure
Commands are sent as JSON with the following structure:
```json
{
  "tool_calls": [{
    "func": "command_name",
    "params": {
      "param1": "value1"
    },
    "messages": [],
    "system_info": ""
  }]
}
```

### Available Commands

#### Device Management
- `list_devices`: Lists all connected RGB devices
  - Returns device names as a formatted string
  - No parameters required

#### Lighting Control
- `set_color`: Sets color for specific or all devices
  - Parameters:
    - `color_name`: Predefined color (see Color Support)
    - `device_name`: Optional device name or "all"
  - Returns success/failure with device-specific messages

- `disable_lighting`: Turns off lighting for all devices
  - No parameters required
  - Sets all devices to "off" mode

- `set_mode`: Sets lighting mode/effect for devices
  - Parameters:
    - `device_name`: Optional device name or "all"
    - `effect_name`: Name of the effect to set
  - Returns success/failure with device-specific messages

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
    'black': (0, 0, 0)
}
```

### Implementation Details

#### OpenRGB Integration
- Uses `OpenRGBClient` for device communication
- Default connection: localhost:6742
- Client name: "G-Assist Plugin"
- Supports device discovery and management
- Handles device-specific modes and effects

#### Response Handling
```python
Response = dict[bool, Optional[str]]
```
- Success response: `{"success": True, "message": "..."}`
- Failure response: `{"success": False, "message": "..."}`

#### Error Handling
- Comprehensive error checking for:
  - OpenRGB connection
  - Device availability
  - Color validation
  - Command parameters
- Detailed logging of operations
- User-friendly error messages

### Logging
- Log file: `%USERPROFILE%\openrgb_plugin.log`
- Log level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Adding New Features
To add new features:
1. Add new command handler function:
   ```python
   def execute_new_command(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
       """Command handler for new feature.
       
       Args:
           params: Command parameters
           context: Message context
           system_info: System information
           
       Returns:
           Response dictionary
       """
       # Implementation
   ```

2. Register the command in `main()`:
   ```python
   commands = {
       # ... existing commands ...
       'new_command': execute_new_command,
   }
   ```

3. Update the manifest.json:
   ```json
   {
     "name": "new_command",
     "description": "Description of the new feature",
     "tags": ["openrgb", "lighting"],
     "properties": {
       "parameter_name": {
         "type": "string",
         "description": "Description of the parameter"
       }
     }
   }
   ```
4. Manually test the function:

   First, run the script:
   ``` bash
   python nanoleaf.py
   ```

   Run the initialize command: 
      ``` json
      {
         "tool_calls" : "initialize"
      }
      ```
   Run the new command:
      ``` json
      {
         "tool_calls" : "new_command", 
         "params": {
            "parameter_name": "parameter_value"
         }
      }
      ```
5. Run the setup & build scripts as outlined above, install the plugin by placing the files in the proper location and test your updated plugin. Use variations of standard user messages to make sure the function is adequately documented in the `manifest.json`

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
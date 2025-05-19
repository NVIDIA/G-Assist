# Nanoleaf Illumination Plugin for G-Assist

Transform your Nanoleaf LED panels into an interactive lighting experience with G-Assist! This plugin lets you control your Nanoleaf lights using simple voice commands or the G-Assist interface. Whether you want to set the mood for a movie night or brighten up your workspace, controlling your Nanoleaf panels has never been easier.

## What Can It Do?
- Change your Nanoleaf panel colors with voice or text commands
- Use natural language: speak or type your commands
- Works with any Nanoleaf device that supports the [Nanoleaf API](https://nanoleafapi.readthedocs.io/en/latest/index.html)
- Seamlessly integrates with your G-Assist setup
- Easy to set up and configure

## Before You Start
Make sure you have:
- Windows PC
- Python 3.x installed on your computer
- Your Nanoleaf device set up and connected to your 2.4GHz WiFi network
- G-Assist installed on your system
- Your Nanoleaf device's IP address 

💡 **Tip**: Nanoleaf devices only work on 2.4GHz networks, not 5GHz. Make sure your device is connected to the correct network band!

💡 **Tip**: Not sure about your Nanoleaf's IP address? You can find it in your router's admin page under connected devices

## Installation Guide

### Step 1: Get the Files
```bash
git clone <repo link>
cd nanoleaf
```
This downloads all the necessary files to your computer.

### Step 2: Set Up Python Environment
Run our setup script to create a virtual environment and install dependencies:

```bash
setup.bat
```

### Step 3: Configure Your Device
1. Find the `config.json` file in the folder
2. Open it with any text editor (like Notepad)
3. Replace the IP address with your Nanoleaf's IP address:
```json
{
  "ip": "192.168.1.100"  # Replace with your Nanoleaf's IP address
}
```

### Step 4: Build the Plugin
```bash
build.bat
```

### Step 5: Install the Plugin
1. Create a new folder here (if it doesn't exist):
   ```
   %programdata%\NVIDIA Corporation\nvtopps\rise\plugins\nanoleaf
   ```
   💡 **Tip**: You can copy this path and paste it into File Explorer's address bar!

2. Copy these three files from the `dist\nanoleaf` folder to the folder you just created:
   - `g-assist-plugin-nanoleaf.exe`
   - `manifest.json`
   - `config.json`

## How to Use
Once everything is set up, you can control your Nanoleaf panels through G-Assist! Try these commands (either by voice or text):
- "Change my room lights to blue"
- "Hey nanoleaf, set my lights to rainbow"
- "/nanoleaf set my lights to red"

💡 **Tip**: You can use either voice commands or type your requests directly into G-Assist - whatever works best for you!

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\nanoleaf.log
```
Check this file for detailed error messages and debugging information.

## Troubleshooting Tips
- **Can't find your Nanoleaf's IP?** Make sure your Nanoleaf is connected to your 2.4GHz WiFi network (5GHz networks are not supported)
- **Commands not working?** Double-check that all three files were copied to the plugins folder & restart G-Assist

## Developer Documentation

### Plugin Architecture
The Nanoleaf plugin is built as a Python-based G-Assist plugin that communicates with Nanoleaf devices using the Nanoleaf API. The plugin follows a command-based architecture where it continuously listens for commands from G-Assist and executes corresponding lighting operations.

### Core Components

#### Command Handling
- `read_command()`: Reads JSON-formatted commands from G-Assist's input pipe
  - Uses Windows API to read from STDIN
  - Returns parsed JSON command or None if invalid
  - Handles chunked input for large messages
  - Logs invalid JSON and exceptions

- `write_response()`: Sends JSON-formatted responses back to G-Assist
  - Uses Windows API to write to STDOUT
  - Appends `<<END>>` marker to indicate message completion
  - Response format: `{"success": bool, "message": Optional[str]}`

#### Configuration
- Configuration is stored in `config.json` in the plugin directory
- Required fields:
  - `ip`: IP address of the Nanoleaf device
- IP address validation ensures proper format
- Configuration is loaded during initialization

#### Available Commands
The plugin supports the following commands:

1. `initialize`
   - Loads configuration from config.json
   - Connects to Nanoleaf device
   - Sets initial color to black
   - Returns success/failure response

2. `shutdown`
   - Gracefully terminates the plugin
   - Powers off Nanoleaf device
   - Returns success response

3. `nanoleaf_change_room_lights`
   - Parameters: `{"color": str}`
   - Supported colors: RED, GREEN, BLUE, CYAN, MAGENTA, YELLOW, BLACK, WHITE, GREY/GRAY, ORANGE, PURPLE/VIOLET, PINK, TEAL, BROWN, ICE_BLUE, CRIMSON, GOLD, NEON_GREEN
   - Special commands: OFF, BRIGHT_UP, BRIGHT_DOWN, RAINBOW
   - Returns success/failure with optional message

4. `nanoleaf_change_profile`
   - Parameters: `{"profile": str}`
   - Sets predefined lighting effects
   - Profile names are case-insensitive
   - Returns success/failure with optional message

### Utility Functions
- `adjust_brightness(nl: Nanoleaf, command: str) -> bool`
  - Adjusts brightness by ±10 levels
  - Supports OFF, BRIGHT_UP, BRIGHT_DOWN commands
  - Returns success status

- `change_color(nl: Nanoleaf, color: str) -> bool`
  - Changes device color using predefined RGB values
  - Returns success status

- `get_rgb_code(color: str) -> tuple[int, int, int] | None`
  - Maps color names to RGB values
  - Returns RGB tuple or None for unknown colors

- `generate_success_response(message: Optional[str] = None) -> Response`
  - Creates standardized success response
  - Optional message for additional context

- `generate_failure_response(message: Optional[str] = None) -> Response`
  - Creates standardized failure response
  - Optional error message for debugging

### Type Definitions
```python
Response = dict[bool, Optional[str]]  # Standard response format
Color = tuple[int, int, int]         # RGB color format
```

### Logging
- Log file location: `%USERPROFILE%\nanoleaf.log`
- Logs all command execution, API calls, and errors
- Includes timestamps and log levels
- Handles logging failures gracefully

### Error Handling
- All commands implement try-catch blocks
- API errors are logged with full details
- Invalid configurations trigger appropriate error responses
- Connection failures are handled gracefully
- Unknown colors/profiles return clear error messages

### Adding New Commands
To add a new command:
1. Implement command function with signature: `def new_command(nl: Nanoleaf, params: dict = None, context: dict = None) -> Response`
2. Add command to `commands` dictionary in `generate_command_handlers()`
3. Implement proper error handling and logging
4. Return standardized response using `generate_success_response()` or `generate_failure_response()`
5. Add the function to the `functions` list in `manifest.json`:
   ```json
   {
      "name": "new_command",
      "description": "Description of what the command does",
      "tags": ["relevant", "tags"],
      "properties": {
      "parameter_name": {
         "type": "string",
         "description": "Description of the parameter"
      }
      }
   }
   ```
6. Manually test the function:

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
7. Run the setup & build scripts as outlined above, install the plugin by placing the files in the proper location and test your updated plugin. Use variations of standard user messages to make sure the function is adequately documented in the `manifest.json`

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
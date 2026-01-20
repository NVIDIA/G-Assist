# Nanoleaf Illumination Plugin for G-Assist

Transform your Nanoleaf LED panels into an interactive lighting experience with G-Assist! This plugin lets you control your Nanoleaf lights using simple voice commands or the G-Assist interface. Whether you want to set the mood for a movie night or brighten up your workspace, controlling your Nanoleaf panels has never been easier.

## What Can It Do?
- Change your Nanoleaf panel colors with voice or text commands
- Use natural language: speak or type your commands
- Works with any Nanoleaf device that supports the [Nanoleaf API](https://nanoleafapi.readthedocs.io/en/latest/index.html)
- Seamlessly integrates with your G-Assist setup
- Interactive setup wizard for first-time configuration

## Before You Start
Make sure you have:
- Windows PC
- Python 3.8 or higher installed
- Your Nanoleaf device set up and connected to your 2.4GHz WiFi network
- G-Assist installed on your system
- Your Nanoleaf device's IP address 

💡 **Tip**: Nanoleaf devices only work on 2.4GHz networks, not 5GHz. Make sure your device is connected to the correct network band!

💡 **Tip**: Not sure about your Nanoleaf's IP address? Check your Wi-Fi app (Google Home, Eero, xFinity, etc.) under connected devices, or your router's admin page

## Installation Guide

### Step 1: Setup
From the `plugins/examples` directory, run:
```bash
setup.bat nanoleaf
```
This installs all required Python packages (`nanoleafapi`) and copies the SDK to `libs/`.

### Step 2: Configure Your Device
1. Find the `config.json` file in the plugin folder
2. Open it with any text editor (like Notepad)
3. Replace the IP address with your Nanoleaf's IP address:
```json
{
  "ip": "192.168.1.100"
}
```

### Step 3: Deploy
Deploy using the setup script:
```bash
setup.bat nanoleaf -deploy
```

Or manually copy the following files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\nanoleaf`:
- `plugin.py`
- `manifest.json`
- `config.json` (with your Nanoleaf IP address configured)
- `libs/` folder (contains dependencies and SDK)

### Step 4: Test with Plugin Emulator
Test your deployed plugin using the emulator:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the nanoleaf plugin from the interactive menu to test the commands.

## How to Use
Once everything is set up, you can control your Nanoleaf panels through G-Assist! Try these commands:
- "Change my room lights to blue"
- "Hey Nanoleaf, set my lights to rainbow"
- "Set my Nanoleaf to red"
- "Activate my gaming profile on Nanoleaf"

💡 **Tip**: You can use either voice commands or type your requests directly into G-Assist - whatever works best for you!

## First-Time Setup
When you first try to use the Nanoleaf plugin without configuration, it will automatically guide you through the setup process with step-by-step instructions displayed directly in G-Assist. Simply ask it to change your lights, and it will:
1. Display setup instructions
2. Guide you to find your Nanoleaf IP address
3. Walk you through pairing your device
4. Verify your configuration
5. **Automatically complete your original request** once setup is done

No manual config editing required unless you prefer it!

## Troubleshooting
| Issue | Solution |
|-------|----------|
| Can't find your Nanoleaf's IP? | Make sure your Nanoleaf is connected to your 2.4GHz WiFi network (5GHz networks are not supported) |
| Commands not working? | Double-check that all files were copied to the plugins folder & restart G-Assist |
| Connection failed? | Verify the IP address is correct and you're on the same network as the Nanoleaf |
| Pairing failed? | Hold the power button on your Nanoleaf for 5-7 seconds to enter pairing mode |

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\nanoleaf\nanoleaf-plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Plugin Architecture
The Nanoleaf plugin is built using the G-Assist SDK (`gassist_sdk`). It uses the `@plugin.command` decorator pattern to register commands that G-Assist can invoke. The plugin communicates with Nanoleaf devices using the `nanoleafapi` library.

### Core Components

#### Plugin Setup
```python
from gassist_sdk import Plugin

plugin = Plugin(
    name="nanoleaf",
    version="2.0.0",
    description="Control Nanoleaf light panels"
)
```

#### Global State
- `NL`: Nanoleaf connection instance
- `NANOLEAF_IP`: Device IP address from config
- `SETUP_COMPLETE`: Whether configuration is valid
- `PENDING_CALL`: Stores command to execute after setup wizard completes

#### Configuration
- Configuration is stored in `config.json` in the plugin directory
- Required fields:
  - `ip`: IP address of the Nanoleaf device
- IP validation: `len(ip) > 5` (shortest valid IP is 7 chars)
- Configuration is loaded on each command execution

### Available Commands

All commands trigger the setup wizard automatically if the plugin is not configured.

1. `nanoleaf_change_room_lights`
   - Parameters: `color: str`
   - Supported colors: RED, GREEN, BLUE, CYAN, MAGENTA, YELLOW, BLACK, WHITE, GREY/GRAY, ORANGE, PURPLE/VIOLET, PINK, TEAL, BROWN, ICE_BLUE, CRIMSON, GOLD, NEON_GREEN
   - Special commands: OFF, BRIGHT_UP, BRIGHT_DOWN, RAINBOW

2. `nanoleaf_change_profile`
   - Parameters: `profile: str`
   - Sets predefined lighting effects (case-insensitive matching)

3. `on_input`
   - Handles user responses during setup wizard
   - Executes pending command after successful configuration

### Setup Wizard Flow
The plugin implements a pending call pattern for seamless first-time setup:

1. User invokes a command (e.g., "set my lights to blue")
2. If not configured, the command is stored via `store_pending_call()`
3. Setup wizard is displayed with `plugin.set_keep_session(True)`
4. User completes configuration and says "next"
5. `on_input` verifies config and calls `execute_pending_call()`
6. Original command executes with `_from_pending=True`

### Utility Functions
- `load_config()`: Loads IP from config.json, sets SETUP_COMPLETE flag
- `ensure_connected()`: Establishes Nanoleaf connection, caches in global `NL`
- `get_rgb_code(color: str)`: Maps color names to RGB tuples
- `store_pending_call(func, **kwargs)`: Saves function call for later execution
- `execute_pending_call()`: Runs stored call with `_from_pending=True`
- `get_setup_instructions()`: Returns formatted setup wizard markdown

### Logging
- Log file location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\nanoleaf\nanoleaf-plugin.log`
- Logs all command execution, API calls, and errors
- Includes timestamps and log levels
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Error Handling
- All commands implement try-except blocks
- Errors are logged before returning user-friendly messages
- Connection failures include troubleshooting steps
- Unknown colors/profiles show available options

### Adding New Commands
To add a new command:

1. Define the function with the `@plugin.command` decorator:
```python
@plugin.command("my_new_command")
def my_new_command(param: str = "", _from_pending: bool = False):
    """Command description."""
    # Check configuration
    load_config()
    if not SETUP_COMPLETE or not NANOLEAF_IP:
        store_pending_call(my_new_command, param=param)
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    # Ensure connection
    if not ensure_connected():
        return "**Connection failed.**..."
    
    # Implement command logic
    try:
        # Your code here
        return "**Success!**"
    except Exception as e:
        logger.error(f"Error: {e}")
        return "**Failed.**..."
```

2. Add the function to `manifest.json`:
```json
{
   "name": "my_new_command",
   "description": "Description of what the command does",
   "tags": ["nanoleaf", "lights"],
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
setup.bat nanoleaf -deploy
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

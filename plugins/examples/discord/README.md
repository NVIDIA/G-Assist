# Discord Integration Plugin for G-Assist

A powerful plugin that enables G-Assist to interact with Discord, allowing you to send messages, charts, and Shadowplay clips directly to your Discord channels. This plugin seamlessly integrates with G-Assist's voice commands to enhance your Discord experience.

## What Can It Do?
- Send text messages to Discord channels
- Share latest G-Assist performance charts (CSV)
- Upload latest NVIDIA ShadowPlay video clips
- Share latest NVIDIA ShadowPlay screenshots
- Automatic setup wizard for first-time configuration

## Before You Start
- G-Assist installed on your system
- Discord Bot Token
- Discord Channel ID
- Python 3.x installed

### Creating a Discord Bot
1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give your app a name
3. Navigate to the "Bot" section in the left sidebar
4. Click "Add Bot" and confirm
5. Under the bot's username, click "Reset Token" to generate a new token
6. Copy the token and save it securely - you'll need it for the `BOT_TOKEN` of the `config.json` file
7. Enable the following Privileged Gateway Intents:
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT
8. Save your changes
9. Make sure your bot is added to your server
   - Installation > Install Link 
   - Copy the install link and make sure it includes the correct permissions
   - `https://discord.com/oauth2/authorize?client_id=<client id>&scope=bot&permissions=2048`

### Getting Your Channel ID
1. Enable Developer Mode in Discord:
   - Go to User Settings > Advanced
   - Enable "Developer Mode"
2. Right-click on your target channel
3. Click "Copy ID" at the bottom of the menu
4. Save this ID for your `config.json`

## Getting Started

### Step 1: Configuration
1. Create a `config.json` file with your Discord credentials:
```json
{
    "BOT_TOKEN": "YOUR_BOT_TOKEN_HERE",
    "CHANNEL_ID": "YOUR_CHANNEL_ID_HERE",
    "GAME_DIRECTORY": "YOUR_GAME_DIRECTORY_HERE"
}
```

`GAME_DIRECTORY` is the target directory from which replay clips and screenshots will be shared. 
- NVIDIA App stores clips and screenshots in a per-application format. e.g. If you record an Instant Replay while playing RUST, the directory where the capture will be saved is `%USERPROFILE%\Videos\NVIDIA\RUST`
   - `"GAME_DIRECTORY": "RUST"`
- To send Desktop captures: `"GAME_DIRECTORY": "Desktop"`

### Step 2: Setup the Plugin Environment
From the `plugins/examples` directory, run the setup script with the plugin name:
```bash
setup.bat discord
```

This will:
- Install pip dependencies from `requirements.txt` to the `libs/` folder
- Copy the G-Assist Python SDK to `libs/gassist_sdk/`

### Step 3: Deploy the Plugin
You can deploy directly using the setup script:
```bash
setup.bat discord -deploy
```

Or manually copy the following files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\discord`:
- `plugin.py`
- `manifest.json`
- `config.json` (with your Discord bot token and channel ID configured)
- `libs/` folder (contains dependencies and SDK)

💡 **Tip**: The `-deploy` flag handles all file copying automatically.

## How to Use
Once everything is set up, you can interact with Discord through simple chat commands.

- "Hey Discord, send a message to my channel saying I'll be there in five minutes"
- "Hey Discord, send the latest perf chart to my channel"
- "Hey Discord, send the latest clip to my channel"
- "Hey Discord, send the latest screenshot to my channel"

## First-Time Setup
When you first try to use the Discord plugin without configuration, it will automatically guide you through the setup process with step-by-step instructions displayed directly in G-Assist. Simply ask the plugin to send a message, and it will:
1. Display setup instructions
2. Guide you to create a Discord bot
3. Help you configure the required settings
4. Verify your configuration

No manual config editing required unless you prefer it!

## Troubleshooting
- **Logs**: Check `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\discord\discord-plugin.log` for detailed logs
- **Configuration**: Verify your `config.json` has correct BOT_TOKEN and CHANNEL_ID

## Developer Documentation

### Plugin Architecture
The Discord plugin is built using the G-Assist Python SDK (V2). It uses a decorator-based command pattern where functions are registered with `@plugin.command()` and the SDK handles all communication with the G-Assist engine.

### Core Components

#### Plugin Setup
```python
from gassist_sdk import Plugin

plugin = Plugin(
    name="discord",
    version="2.0.0",
    description="Send messages and media to Discord"
)
```

#### Command Registration
Commands are registered using the `@plugin.command()` decorator:
```python
@plugin.command("send_message_to_discord_channel")
def send_message_to_discord_channel(message: str = ""):
    """Send a text message to Discord channel."""
    # Implementation here
    return "Message sent!"
```

#### Configuration
- Configuration is stored in `config.json` at `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\discord\config.json`
- Required fields:
  - `BOT_TOKEN`: Discord bot authentication token
  - `CHANNEL_ID`: Target Discord channel ID
  - `GAME_DIRECTORY`: Directory name for game-specific captures

#### Available Commands
The plugin supports the following commands:

1. `send_message_to_discord_channel`
   - Parameters: `{"message": str}`
   - Sends text message to configured Discord channel
   - Returns success/failure message

2. `send_latest_chart_to_discord_channel`
   - Parameters: `{"caption": Optional[str]}`
   - Finds and sends latest CSV from G-Assist charts directory
   - Directory: `%USERPROFILE%\Videos\NVIDIA\G-Assist`

3. `send_latest_shadowplay_clip_to_discord_channel`
   - Parameters: `{"caption": Optional[str]}`
   - Finds and sends latest MP4 from game-specific directory
   - Directory: `%USERPROFILE%\Videos\NVIDIA\{GAME_DIRECTORY}`

4. `send_latest_screenshot_to_discord_channel`
   - Parameters: `{"caption": Optional[str]}`
   - Finds and sends latest PNG from game-specific directory
   - Directory: `%USERPROFILE%\Videos\NVIDIA\{GAME_DIRECTORY}`

### Utility Functions
- `find_latest_file(directory: str, extension: str) -> Optional[str]`
  - Finds most recently modified file with given extension
  - Returns full file path or None if no files found

- `load_config()`
  - Loads Discord bot configuration from config.json
  - Sets global BOT_TOKEN, CHANNEL_ID, and GAME_DIRECTORY

### Logging
- Log file location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\discord\discord-plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Captures all command execution, API calls, and errors

### Error Handling
- All commands implement try-except blocks
- API errors are logged with full response text
- File operations include existence checks
- Invalid configurations trigger the setup wizard automatically

### Adding New Commands
To add a new command:

1. Create a new function with the `@plugin.command()` decorator:
```python
@plugin.command("new_command")
def new_command(param_name: str = ""):
    """Description of what the command does."""
    # Load config if needed
    load_config()
    
    # Implement your logic
    try:
        # Your code here
        return "Success message to display"
    except Exception as e:
        logger.error(f"Error: {e}")
        return "Error message to display"
```

2. Add the function to the `functions` list in `manifest.json`:
```json
{
   "name": "new_command",
   "description": "Description of what the command does",
   "tags": ["relevant", "tags"],
   "properties": {
      "param_name": {
         "type": "string",
         "description": "Description of the parameter"
      }
   }
}
```

3. Test locally by running:
```bash
python plugin.py
```
The plugin will start and listen for commands from stdin (useful for debugging).

4. Deploy the plugin:
```bash
setup.bat discord -deploy
```

5. Test using the plugin emulator from the `plugins` directory:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the discord plugin from the interactive menu to test your new function.

6. Test with G-Assist by using voice or text commands to trigger your new function.

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

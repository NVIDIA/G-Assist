# Discord Integration Plugin for G-Assist

A powerful plugin that enables G-Assist to interact with Discord, allowing you to send messages, charts, and Shadowplay clips directly to your Discord channels. This plugin seamlessly integrates with G-Assist's voice commands to enhance your Discord experience.

## What Can It Do?
- Send text messages to Discord channels
- Share latest G-Assist charts (csv)
- Upload latest NVIDIA App video clips
- Secure token-based authentication
- Comprehensive logging for debugging

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
Run the setup script:
```bash
setup.bat
```

### Step 3: Build the Plugin
Run the build script:
```bash
build.bat
```

### Step 3: Install the Plugin
1. Paste the `discord` folder to the the G-Assist plugins directory:
   ```
   %programdata%\NVIDIA Corporation\nvtopps\rise\plugins
   ```
2. Ensure the following files are located in this directory:
   - g-assist-plugin-discord.exe
   - config.json
   - manifest.json

## How to Use
Once everything is set up, you can interact with Discord through simple chat commands.

- `Hey Discord, send a message to my channel saying I'll be there in five minutes`
- `Hey Discord, send the latest perf chart to my channel`
- `Hey Discord, send the latest clip to my channel`
- `Hey Discord, send the latest screenshot to my channel`

## Troubleshooting
- **Logs**: Check `%USERPROFILE%\discord-plugin.log` for detailed logs
- **Configuration**: Verify your `config.json` has correct BOT_TOKEN and CHANNEL_ID

## Developer Documentation

### Plugin Architecture
The Discord plugin is built as a Python-based G-Assist plugin that communicates with Discord's API. The plugin follows a command-based architecture where it continuously listens for commands from G-Assist and executes corresponding Discord operations.

### Core Components

#### Command Handling
- `read_command()`: Reads JSON-formatted commands from G-Assist's input pipe
  - Uses Windows API to read from STDIN
  - Returns parsed JSON command or None if invalid
  - Handles chunked input for large messages

- `write_response()`: Sends JSON-formatted responses back to G-Assist
  - Uses Windows API to write to STDOUT
  - Appends `<<END>>` marker to indicate message completion
  - Response format: `{"success": bool, "message": Optional[str]}`

#### Configuration
- Configuration is stored in `config.json` at `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\discord\config.json`
- Required fields:
  - `BOT_TOKEN`: Discord bot authentication token
  - `CHANNEL_ID`: Target Discord channel ID
  - `GAME_DIRECTORY`: Directory name for game-specific captures

#### Available Commands
The plugin supports the following commands:

1. `initialize`
   - Loads configuration from config.json
   - Sets up global bot token and channel ID
   - Returns success/failure response
   - Called before every command to make sure config is set up correctly

2. `shutdown`
   - Gracefully terminates the plugin
   - Returns success response

3. `send_message_to_discord_channel`
   - Parameters: `{"message": str}`
   - Sends text message to configured Discord channel
   - Returns success/failure with optional message

4. `send_latest_chart_to_discord_channel`
   - Parameters: `{"caption": Optional[str]}`
   - Finds and sends latest CSV from G-Assist charts directory
   - Directory: `%USERPROFILE%\Videos\NVIDIA\G-Assist`

5. `send_latest_shadowplay_clip_to_discord_channel`
   - Parameters: `{"caption": Optional[str]}`
   - Finds and sends latest MP4 from game-specific directory
   - Directory: `%USERPROFILE%\Videos\NVIDIA\{GAME_DIRECTORY}`

6. `send_latest_screenshot_to_discord_channel`
   - Parameters: `{"caption": Optional[str]}`
   - Finds and sends latest PNG from game-specific directory
   - Directory: `%USERPROFILE%\Videos\NVIDIA\{GAME_DIRECTORY}`

### Utility Functions
- `find_latest_file(directory: str, extension: str) -> Optional[str]`
  - Finds most recently modified file with given extension
  - Returns full file path or None if no files found

- `generate_success_response(message: Optional[str] = None) -> Response`
  - Creates standardized success response
  - Optional message for additional context

- `generate_failure_response(message: Optional[str] = None) -> Response`
  - Creates standardized failure response
  - Optional error message for debugging

### Logging
- Log file location: `%USERPROFILE%\discord-plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Captures all command execution, API calls, and errors

### Error Handling
- All commands implement try-catch blocks
- API errors are logged with full response text
- File operations include existence checks
- Invalid configurations trigger appropriate error responses

### Adding New Commands
To add a new command:
1. Implement command function with signature: `def new_command(params: dict = None, context: dict = None, system_info: dict = None) -> dict`
2. Add command to `commands` dictionary in `main()`
3. Implement proper error handling and logging
4. Return standardized response using `generate_success_response()` or `generate_failure_response()`
5. Add the function to the `functions` list in `manifest.json` file: 
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
   python plugin.py
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
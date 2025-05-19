# G-Assist Plugin - IFTTT

Control your IFTTT applets through G-Assist using natural language commands! This plugin allows you to trigger IFTTT applets and manage your smart home devices using voice commands.

## Features
- Trigger IFTTT applets with voice commands
- Control smart home devices
- Send notifications
- Interact with various IFTTT services
- Secure API key management
- Automatic IGN gaming news headlines delivery

## Requirements
- Python 3.12 or higher
- IFTTT account with Webhooks service enabled
- IFTTT Webhook API key

## Installation Guide

### Step 1: Get the Files
```bash
git clone <repo-name>
```

### Step 2: Set Up Python Environment
```bash
setup.bat
```

### Step 3: Build the Plugin
```bash
build.bat
```

### Step 4: Install the Plugin
Copy the `dist/ifttt` folder to the proper directory: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins`

### Step 5: Configure RSS Feeds (Optional)
Edit the `config.json` file in the plugin directory to customize your RSS feed sources:
```json
{
  "webhook_key": "YOUR_WEBHOOK_KEY",
  "event_name": "game_routine",
  "main_rss_url": "https://feeds.feedburner.com/ign/pc-articles",
  "alternate_rss_url": "https://feeds.feedburner.com/ign/all"
}
```

### How to Use
- `Hey IFTTT, it's game time!`

- `/ifttt what applets do I have?`

## game_routine Components
### 1. Spotify 
Starts Spotify playback

**Note**: Spotify playback must be active, recently toggled off/on  

### 2. IGN Gaming News Integration
This plugin will:
1. Automatically fetch the latest gaming news headlines from IGN using the configured RSS feeds
2. Include up to 3 news headlines in your IFTTT notification
3. Send them as value1, value2, and value3 in the webhook data

### 3. TP-Link Kasa
Turns TP-Link Kasa smart plug on

You can use these values in your IFTTT applet to format and display the news in your notifications.

## IFTTT Documentation
This plugin uses the IFTTT Webhooks service to trigger applets. For more information about IFTTT and its capabilities, visit:
- [IFTTT Documentation](https://ifttt.com/docs)
- [IFTTT Webhooks Service](https://ifttt.com/maker_webhooks)

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\ifttt_plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Plugin Architecture
The IFTTT plugin is built as a Python-based G-Assist plugin that communicates with IFTTT's API. The plugin follows a command-based architecture where it continuously listens for commands from G-Assist and executes corresponding IFTTT operations.

### IFTTT Integration
The plugin integrates with IFTTT through the Webhooks service:

1. Webhook URL Format:
```
https://maker.ifttt.com/trigger/{EVENT_NAME}/with/key/{WEBHOOK_KEY}
```

2. Webhook Data Format:
```json
{
    "value1": "First news headline",
    "value2": "Second news headline",
    "value3": "Third news headline"
}
```

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
- Configuration is loaded from `config.json` located at:
  ```
  %PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\ifttt\config.json
  ```
- Required configuration parameters:
  - `webhook_key`: Your IFTTT Webhook API key
  - `event_name`: The IFTTT event name to trigger
  - `main_rss_url`: Primary RSS feed URL (defaults to IGN PC Gaming feed)
  - `alternate_rss_url`: Fallback RSS feed URL (defaults to IGN All feed)

### Available Commands

#### `initialize`
Initializes the plugin and sets up the environment.
- No parameters required
- Returns success response with initialization status

#### `shutdown`
Gracefully shuts down the plugin.
- No parameters required
- Returns success response with shutdown status

#### `trigger_gaming_setup`
Triggers the IFTTT applet with gaming news integration.
- Automatically fetches latest gaming news from IGN
- Includes up to 3 news headlines in the webhook data
- Parameters: None (uses configuration from config.json)
- Returns success/failure response with status message

#### Logging
- Log file location: `%USERPROFILE%\ifttt_plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Error Handling
- All operations are wrapped in try-except blocks
- Errors are logged to the log file
- Failed operations return a failure response with an error message
- Network errors during IFTTT webhook calls are caught and reported
- RSS feed failures trigger fallback to alternate feed

### Dependencies
- Python 3.12+
- Required Python packages:
  - requests: For HTTP requests to IFTTT
  - feedparser: For RSS feed parsing
  - Standard library modules: json, logging, os, ctypes

### Command Processing
The plugin processes commands through a JSON-based protocol:

1. Input Format:
```json
{
    "tool_calls": [
        {
            "func": "command_name",
            "params": {
                "param1": "value1",
                "param2": "value2"
            }
        }
    ]
}
```

2. Output Format:
```json
{
    "success": true|false,
    "message": "Optional message"
}
```

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
# Twitch Status Plugin for NVIDIA G-Assist

Transform your G-Assist experience with real-time Twitch stream status checking! This plugin lets you monitor your favorite Twitch streamers directly through the G-Assist platform. Whether you want to know if your favorite streamer is live or get details about their current stream, checking Twitch status has never been easier.

## What Can It Do?
- Check if any Twitch streamer is currently live
- Get detailed stream information including:
  - Stream title
  - Game being played
  - Current viewer count
  - Stream start time
- Detailed logging for troubleshooting

## Before You Start
Make sure you have:
- Windows PC
- Python 3.8 or higher installed
- Twitch Developer Application credentials - Visit the [Twitch Developer Console](https://dev.twitch.tv/console) to create them
- NVIDIA G-Assist installed

## Installation Guide

### Step 1: Set up your Twitch App
- Register an application. Follow directions here: https://dev.twitch.tv/docs/authentication/register-app 
    - Set OAuth Redirect URLs to http://localhost:3000
    - Set Category to Application Integration
- From your Developer Console, in the “Applications” tab, locate your app under “Developer Applications”, and click “Manage”.
- Copy Client ID and Client Secret and paste to the `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` values in the `config.json file` 

### Step 2: Setup and Deploy
From the `plugins/examples` directory, run:
```bash
setup.bat twitch
```
This installs dependencies to the `libs/` folder and copies the G-Assist SDK.

To deploy the plugin to G-Assist:
```bash
setup.bat twitch -deploy
```

💡 **Tip**: Make sure G-Assist is closed when deploying!

## How to Use
Once everything is set up, you can check Twitch stream status through simple chat commands.

Try these commands:
- "Hey Twitch, is Ninja live?"
- "Check if shroud is streaming"
- "Is pokimane online right now?"
- "Is xQc streaming?"

### Example Responses

When a streamer is live:
```text
**ninja** is **LIVE**!

**Title:** Friday Fortnite!
**Game:** Fortnite
**Viewers:** 45,231
**Started:** 2024-03-14T12:34:56Z
```

When a streamer is offline:
```
**shroud** is currently **offline**. Check back later!
```

## First-Time Setup
When you first try to use the Twitch plugin without configuration, it will automatically guide you through the setup process with step-by-step instructions displayed directly in G-Assist. Simply ask it to check a streamer's status (e.g., "is ninja streaming?"), and it will:
1. Open the Twitch Developer Console for you
2. Guide you through creating a Twitch app (Step 1/2)
3. Help you configure your credentials in the config file (Step 2/2)
4. Verify your configuration and **automatically complete your original request**

Just say **"next"** or **"continue"** to move between steps. The setup takes about 5 minutes and once complete, your original query is executed automatically!

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Failed to authenticate" errors | Verify your Client ID and Secret in config.json |
| Setup wizard keeps appearing | Make sure you saved the config file after adding credentials |
| Plugin not loading | Verify files are deployed and restart G-Assist |
| OAuth token expired | The plugin automatically refreshes tokens; if issues persist, check credentials |

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\twitch\twitch-plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Architecture Overview

The Twitch plugin is built using the **G-Assist SDK (Protocol V2)**, which handles all communication with G-Assist via JSON-RPC 2.0. The SDK abstracts away the protocol details so you can focus on business logic.

### Project Structure

```
twitch/
├── plugin.py           # Main plugin code using gassist_sdk
├── manifest.json       # Plugin configuration (protocol_version: "2.0")
├── config.json         # Twitch API credentials (add to .gitignore!)
├── requirements.txt    # Python dependencies
├── libs/               # SDK folder (auto-added to PYTHONPATH)
│   └── gassist_sdk/    # G-Assist Plugin SDK
└── README.md
```

### Manifest File (`manifest.json`)

```json
{
    "manifestVersion": 1,
    "name": "twitch",
    "description": "Check Twitch stream status",
    "executable": "plugin.py",
    "persistent": true,
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "check_twitch_live_status",
            "description": "Checks if a Twitch user is live and retrieves stream details.",
            "tags": ["twitch", "live", "streaming"],
            "properties": {
                "username": {
                    "type": "string",
                    "description": "The Twitch username to check."
                }
            }
        }
    ]
}
```

### Plugin Code (`plugin.py`)

The SDK handles all protocol communication automatically:

```python
import os
import sys
import json
import logging
import requests

# SDK import (from libs/ folder)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

from gassist_sdk import Plugin, Context

# Configuration
PLUGIN_NAME = "twitch"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Twitch API endpoints
TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAM_URL = "https://api.twitch.tv/helix/streams"

# Create plugin instance
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Check Twitch stream status"
)

def load_config() -> dict:
    """Load Twitch API credentials from config file."""
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    return {}

def get_oauth_token(config: dict) -> str:
    """Obtain OAuth token from Twitch."""
    try:
        response = requests.post(
            TWITCH_OAUTH_URL,
            params={
                "client_id": config.get("TWITCH_CLIENT_ID"),
                "client_secret": config.get("TWITCH_CLIENT_SECRET"),
                "grant_type": "client_credentials"
            }
        )
        return response.json().get("access_token")
    except Exception as e:
        logger.error(f"Error getting OAuth token: {e}")
        return None

@plugin.command("check_twitch_live_status")
def check_twitch_live_status(username: str, context: Context = None):
    """
    Check if a Twitch user is currently live streaming.
    
    Args:
        username: The Twitch username to check
        context: Conversation context (provided by engine)
    
    Returns:
        Stream status message
    """
    logger.info(f"Checking status for: {username}")
    
    config = load_config()
    if not config.get("TWITCH_CLIENT_ID"):
        return "**Setup Required:** Please configure your Twitch API credentials in config.json"
    
    oauth_token = get_oauth_token(config)
    if not oauth_token:
        return "**Error:** Failed to authenticate with Twitch API"
    
    try:
        headers = {
            "Client-ID": config.get("TWITCH_CLIENT_ID"),
            "Authorization": f"Bearer {oauth_token}"
        }
        
        response = requests.get(
            TWITCH_STREAM_URL,
            headers=headers,
            params={"user_login": username}
        )
        
        data = response.json().get("data", [])
        if data:
            stream = data[0]
            return f"""**{username}** is **LIVE**!

**Title:** {stream['title']}
**Game:** {stream.get('game_name', 'Unknown')}
**Viewers:** {stream['viewer_count']:,}
**Started:** {stream.get('started_at', 'Unknown')}"""
        
        return f"**{username}** is currently **offline**. Check back later!"
        
    except Exception as e:
        logger.error(f"Error checking stream status: {e}")
        return f"**Error:** Could not check stream status for {username}"

if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin...")
    plugin.run()
```

### Key SDK Features Used

| Feature | Description |
|---------|-------------|
| `@plugin.command()` | Decorator to register command handlers |
| `plugin.run()` | Starts the plugin main loop (handles all protocol communication) |
| `plugin.stream()` | Send streaming output during long operations |
| `plugin.set_keep_session()` | Enable passthrough mode for multi-turn conversations |

### Protocol V2 Benefits

The SDK handles all protocol details automatically:
- ✅ JSON-RPC 2.0 with length-prefixed framing
- ✅ Automatic ping/pong responses (no heartbeat code needed!)
- ✅ Error handling and graceful shutdown
- ✅ No need to implement pipe communication manually

### Configuration (`config.json`)

```json
{
    "TWITCH_CLIENT_ID": "your_client_id_here",
    "TWITCH_CLIENT_SECRET": "your_client_secret_here"
}
```

### Testing

1. **Local test** - Run directly to check for syntax errors:
   ```bash
   python plugin.py
   ```

2. **Deploy** - From `plugins/examples` directory:
   ```bash
   setup.bat twitch -deploy
   ```

3. **Plugin emulator** - Test commands without G-Assist:
   ```bash
   python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
   ```
   Then select the twitch plugin and test commands interactively.

4. **G-Assist test** - Open G-Assist and try: "Is ninja streaming?"

### Adding New Commands

1. Add a new function with the `@plugin.command()` decorator:
   ```python
   @plugin.command("get_channel_info")
   def get_channel_info(username: str, context: Context = None):
       """Get channel information for a Twitch user."""
       # Your implementation
       return "Channel info here"
   ```

2. Add the function to `manifest.json`:
   ```json
   {
       "name": "get_channel_info",
       "description": "Get channel information for a Twitch user",
       "tags": ["twitch", "channel", "info"],
       "properties": {
           "username": {
               "type": "string",
               "description": "The Twitch username"
           }
       }
   }
   ```

3. Deploy with `setup.bat twitch -deploy` and test!

### Pro Tips

- **Security**: Store API credentials in `config.json` and add it to `.gitignore`
- **Logging**: Check `twitch-plugin.log` for debugging
- **Streaming**: Use `plugin.stream()` for long operations to show progress
- **Passthrough**: Use `plugin.set_keep_session(True)` for interactive conversations

### Next Steps

Ideas for feature enhancements:
- Add channel information retrieval
- Implement stream analytics
- Add top games listing
- Create clip management features

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the [Twitch API](https://dev.twitch.tv/docs/api/)
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
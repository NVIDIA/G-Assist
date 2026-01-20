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

### Step 2: Setup
From the `examples/` folder, run:
```bash
setup.bat ifttt
```
This installs all required Python packages and copies the SDK to `libs/`.

### Step 3: Install the Plugin
Copy the entire `ifttt` folder to:
```bash
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins
```

💡 **Tip**: Python plugins run directly—no build step required! Make sure all files are copied, including:
- `plugin.py` (main plugin script)
- `manifest.json`
- `config.json` (you'll need to update this with your IFTTT credentials)
- `libs/` folder (contains the G-Assist SDK)

### Step 5: Configure Your IFTTT Webhook
1. Get your IFTTT Webhook key from [https://ifttt.com/maker_webhooks/settings](https://ifttt.com/maker_webhooks/settings)
2. Open `config.json` in the plugin directory
3. Add your webhook key and configure the settings:
```json
{
  "webhook_key": "YOUR_WEBHOOK_KEY",
  "event_name": "game_routine",
  "main_rss_url": "https://feeds.feedburner.com/ign/pc-articles",
  "alternate_rss_url": "https://feeds.feedburner.com/ign/all"
}
```

## How to Use
Once everything is set up, you can trigger your IFTTT applets through G-Assist! Try these commands:
- "Hey IFTTT, it's game time!"
- "Activate my gaming setup"
- "Start my game routine"

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

## First-Time Setup
When you first try to use the IFTTT plugin without configuration, it will automatically guide you through the setup process with step-by-step instructions displayed directly in G-Assist. Simply try to trigger an applet, and it will:
1. Open the IFTTT website for you to create an account or log in
2. Open the config file for you to paste your credentials
3. Guide you through getting your webhook key
4. **Complete your original request** after setup is done

Just say **"next"** or **"continue"** when you've saved your config, and the plugin will automatically execute whatever you originally asked for!

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\ifttt\ifttt-plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Architecture Overview

The IFTTT plugin is built using the **G-Assist SDK (Protocol V2)**, which handles all communication with G-Assist via JSON-RPC 2.0. The SDK abstracts away the protocol details so you can focus on business logic.

### Project Structure

```
ifttt/
├── plugin.py           # Main plugin code using gassist_sdk
├── manifest.json       # Plugin configuration (protocol_version: "2.0")
├── config.json         # IFTTT credentials (add to .gitignore!)
├── requirements.txt    # Python dependencies
├── libs/               # SDK folder (auto-added to PYTHONPATH)
│   └── gassist_sdk/    # G-Assist Plugin SDK
└── README.md
```

### Manifest File (`manifest.json`)

```json
{
    "manifestVersion": 1,
    "name": "ifttt",
    "version": "2.0.0",
    "description": "Trigger IFTTT events",
    "executable": "plugin.py",
    "persistent": true,
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "trigger_gaming_setup",
            "description": "Triggers your custom IFTTT gaming setup",
            "tags": ["gaming", "ifttt", "automation"],
            "properties": {
                "event_name": {
                    "type": "string",
                    "description": "The IFTTT event name to trigger"
                }
            }
        }
    ]
}
```

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

### Plugin Code (`plugin.py`)

The SDK handles all protocol communication automatically:

```python
import os
import sys
import json
import logging
import requests
import feedparser

# SDK import (from libs/ folder)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

from gassist_sdk import Plugin, Context

# Configuration
PLUGIN_NAME = "ifttt"
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

# Create plugin instance
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Trigger IFTTT events"
)

def load_config() -> dict:
    """Load IFTTT configuration from config file."""
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    return {}

def get_news_headlines(config: dict) -> list:
    """Fetch latest gaming news from RSS feed."""
    try:
        feed = feedparser.parse(config.get("main_rss_url", ""))
        headlines = [entry.title for entry in feed.entries[:3]]
        if not headlines:
            feed = feedparser.parse(config.get("alternate_rss_url", ""))
            headlines = [entry.title for entry in feed.entries[:3]]
        return headlines
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []

@plugin.command("trigger_gaming_setup")
def trigger_gaming_setup(event_name: str = "", context: Context = None):
    """
    Trigger IFTTT gaming setup with news headlines.
    
    Args:
        event_name: Optional override for event name
        context: Conversation context (provided by engine)
    
    Returns:
        Status message
    """
    config = load_config()
    
    if not config.get("webhook_key"):
        plugin.set_keep_session(True)
        return "**Setup Required:** Please configure your IFTTT webhook key in config.json"
    
    webhook_key = config.get("webhook_key")
    event = event_name or config.get("event_name", "game_routine")
    
    logger.info(f"Triggering IFTTT event: {event}")
    
    try:
        # Fetch news headlines for webhook data
        headlines = get_news_headlines(config)
        data = {
            "value1": headlines[0] if len(headlines) > 0 else "",
            "value2": headlines[1] if len(headlines) > 1 else "",
            "value3": headlines[2] if len(headlines) > 2 else ""
        }
        
        # Trigger IFTTT webhook
        url = f"https://maker.ifttt.com/trigger/{event}/with/key/{webhook_key}"
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        
        return f"🎮 **Gaming setup activated!**\n\nTriggered event: `{event}`"
        
    except Exception as e:
        logger.error(f"Error triggering IFTTT: {e}")
        return f"**Error:** Failed to trigger IFTTT event: {e}"

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
| `plugin.set_keep_session()` | Enable passthrough mode for setup wizards |

### Protocol V2 Benefits

The SDK handles all protocol details automatically:
- ✅ JSON-RPC 2.0 with length-prefixed framing
- ✅ Automatic ping/pong responses (no heartbeat code needed!)
- ✅ Error handling and graceful shutdown
- ✅ No need to implement pipe communication manually

### Configuration (`config.json`)

```json
{
    "webhook_key": "YOUR_WEBHOOK_KEY",
    "event_name": "game_routine",
    "main_rss_url": "https://feeds.feedburner.com/ign/pc-articles",
    "alternate_rss_url": "https://feeds.feedburner.com/ign/all"
}
```

### Logging

- Log file location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\ifttt\ifttt-plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Adding New Commands

1. Add a new function with the `@plugin.command()` decorator:
   ```python
   @plugin.command("trigger_custom_event")
   def trigger_custom_event(event_name: str, value1: str = "", context: Context = None):
       """Trigger a custom IFTTT event."""
       # Your implementation
       return "Event triggered!"
   ```

2. Add the function to `manifest.json`:
   ```json
   {
       "name": "trigger_custom_event",
       "description": "Trigger a custom IFTTT event",
       "tags": ["ifttt", "automation", "custom"],
       "properties": {
           "event_name": {
               "type": "string",
               "description": "The IFTTT event name to trigger"
           },
           "value1": {
               "type": "string",
               "description": "Optional data value"
           }
       },
       "required": ["event_name"]
   }
   ```

3. Test locally by running `python plugin.py` and using the plugin emulator

4. Deploy by copying the folder to the plugins directory


## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
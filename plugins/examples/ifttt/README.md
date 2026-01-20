# G-Assist Plugin - IFTTT

Control your IFTTT applets through G-Assist using natural language commands! This plugin allows you to trigger IFTTT applets and manage your smart home devices using voice commands.

## Features
- Trigger IFTTT applets with voice commands
- Control smart home devices
- Send notifications
- Interact with various IFTTT services
- Automatic IGN gaming news headlines delivery
- Interactive setup wizard for first-time configuration

## Requirements
- Python 3.8 or higher
- IFTTT account with Webhooks service enabled
- IFTTT Webhook API key

## Installation Guide

### Step 1: Setup
From the `plugins/examples` directory, run:
```bash
setup.bat ifttt
```
This installs all required Python packages and copies the SDK to `libs/`.

### Step 2: Configure Your IFTTT Webhook
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

### Step 3: Deploy
Deploy using the setup script:
```bash
setup.bat ifttt -deploy
```

Or manually copy the following files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\ifttt`:
- `plugin.py`
- `manifest.json`
- `config.json` (with your IFTTT credentials configured)
- `libs/` folder (contains the G-Assist SDK and dependencies)

### Step 4: Test with Plugin Emulator
Test your deployed plugin using the emulator:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the ifttt plugin from the interactive menu to test the commands.

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

## Troubleshooting
- **Logs**: Check `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\ifttt\ifttt-plugin.log` for detailed logs
- **Configuration**: Verify your `config.json` has correct webhook_key and event_name
- **Connection Issues**: Ensure you have an active internet connection

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

### Core Components

#### Plugin Setup
```python
from gassist_sdk import Plugin

plugin = Plugin(
    name="ifttt",
    version="2.0.0",
    description="IFTTT webhook trigger with gaming news"
)
```

#### Command Registration
Commands are registered using the `@plugin.command()` decorator:
```python
@plugin.command("trigger_gaming_setup")
def trigger_gaming_setup(_from_pending: bool = False):
    """Trigger IFTTT gaming setup applet with latest gaming news."""
    load_config()
    
    if not SETUP_COMPLETE:
        store_pending_call(trigger_gaming_setup)
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    # Fetch news and trigger webhook
    headlines = fetch_ign_gaming_news()
    # ... trigger IFTTT webhook
    return "Gaming setup triggered!"
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

### Configuration (`config.json`)

```json
{
    "webhook_key": "YOUR_WEBHOOK_KEY",
    "event_name": "game_routine",
    "main_rss_url": "https://feeds.feedburner.com/ign/pc-articles",
    "alternate_rss_url": "https://feeds.feedburner.com/ign/all"
}
```

### Key SDK Features Used

| Feature | Description |
|---------|-------------|
| `@plugin.command()` | Decorator to register command handlers |
| `plugin.run()` | Starts the plugin main loop (handles all protocol communication) |
| `plugin.stream()` | Send streaming output during long operations |
| `plugin.set_keep_session()` | Enable passthrough mode for setup wizards |

### Logging

- Log file location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\ifttt\ifttt-plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Adding New Commands

1. Add a new function with the `@plugin.command()` decorator:
```python
@plugin.command("trigger_custom_event")
def trigger_custom_event(event_name: str = ""):
    """Trigger a custom IFTTT event."""
    load_config()
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
        }
    },
    "required": ["event_name"]
}
```

3. Deploy the plugin:
```bash
setup.bat ifttt -deploy
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

"""
Discord Plugin for G-Assist - V2 SDK Version

Send messages, clips, and screenshots to Discord channels.
"""

import os
import sys

# ============================================================================
# PATH SETUP - Must be FIRST before any third-party imports!
# ============================================================================
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# Now we can import third-party libraries
import json
import logging
from typing import Optional

import requests

try:
    from gassist_sdk import Plugin
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "discord"
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
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories for media files
CSV_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), "Videos", "NVIDIA", "G-Assist")
BASE_MP4_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), "Videos", "NVIDIA")
BASE_SCREENSHOT_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), "Videos", "NVIDIA")

# ============================================================================
# GLOBAL STATE
# ============================================================================
BOT_TOKEN: Optional[str] = None
CHANNEL_ID: Optional[str] = None
GAME_DIRECTORY: Optional[str] = None
SETUP_COMPLETE = False


def load_config():
    """Load Discord bot configuration."""
    global BOT_TOKEN, CHANNEL_ID, GAME_DIRECTORY, SETUP_COMPLETE
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        BOT_TOKEN = config.get("BOT_TOKEN", "")
        CHANNEL_ID = config.get("CHANNEL_ID", "")
        GAME_DIRECTORY = config.get("GAME_DIRECTORY", "")
        
        if BOT_TOKEN and len(BOT_TOKEN) > 20 and CHANNEL_ID and len(CHANNEL_ID) > 10:
            SETUP_COMPLETE = True
            logger.info(f"Successfully loaded config from {CONFIG_FILE}")
        else:
            logger.warning("Bot token or channel ID is empty/invalid")
            BOT_TOKEN = None
            CHANNEL_ID = None
    except FileNotFoundError:
        logger.error(f"Config file not found at {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error loading config: {e}")


def get_setup_instructions() -> str:
    """Return setup wizard instructions."""
    return f"""_
**Discord Plugin - First Time Setup**

Welcome! Let's get you connected to Discord. This takes about **5 minutes**.

---

**Step 1: Create Your Discord Bot**

1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and name it (e.g., "G-Assist Bot")
3. Go to the **Bot** tab and click **Add Bot**
4. Click **Reset Token** and copy it — you'll need this soon
5. Enable these **Privileged Gateway Intents**:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
6. Click **Save Changes**

---

**Step 2: Add Bot to Your Server**

1. Go to the **Installation** tab
2. Copy the install link and open it in your browser
3. Select your server and authorize the bot

---

**Step 3: Get Your Channel ID**

1. In Discord, go to **User Settings** → **Advanced**
2. Enable **Developer Mode**
3. Right-click your target channel → **Copy Channel ID**

---

**Step 4: Configure the Plugin**

Open the config file at:
```
{CONFIG_FILE}
```

Update it with your values:
```
{{
  "BOT_TOKEN": "paste_your_bot_token_here",
  "CHANNEL_ID": "paste_your_channel_id_here",
  "GAME_DIRECTORY": "Desktop"
}}
```

_(Set `GAME_DIRECTORY` to your game folder: "Desktop", "RUST", etc.)_

Save the file and try the command again!\r"""


def find_latest_file(directory: str, extension: str) -> Optional[str]:
    """Find the most recently modified file with given extension."""
    try:
        if not os.path.exists(directory):
            logger.error(f"Directory not found: {directory}")
            return None
        files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(extension)]
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception as e:
        logger.error(f"Error finding latest file: {str(e)}")
        return None


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Send messages and media to Discord"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("send_message_to_discord_channel")
def send_message_to_discord_channel(message: str = ""):
    """
    Send a text message to Discord channel.
    
    Args:
        message: The text message to send
    """
    global BOT_TOKEN, CHANNEL_ID, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not message:
        return "No message provided. Please include a message to send."
    
    plugin.stream("Sending message to Discord...")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    payload = {"content": message}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code in [200, 201]:
            logger.info("Message sent successfully.")
            return "Message sent successfully!"
        else:
            logger.error(f"Failed to send message: {r.text}")
            return "Failed to send message. Please check your bot token and channel ID in the configuration."
    except Exception as e:
        logger.error(f"Error in send_message_to_discord_channel: {str(e)}")
        return "Unable to send message. Please check your internet connection and try again."


@plugin.command("send_latest_chart_to_discord_channel")
def send_latest_chart_to_discord_channel(caption: str = ""):
    """
    Send latest performance chart (CSV) to Discord.
    
    Args:
        caption: Optional caption for the file
    """
    global BOT_TOKEN, CHANNEL_ID, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    plugin.stream("Finding latest chart...")
    
    file_path = find_latest_file(CSV_DIRECTORY, ".csv")
    if not file_path:
        return "No performance chart found. Charts are created when you record performance data in G-Assist."
    
    plugin.stream("Uploading chart to Discord...")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            payload = {"content": caption}
            r = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        
        if r.status_code in [200, 201]:
            return "Chart sent successfully!"
        else:
            logger.error(f"Failed to send chart: {r.text}")
            return "Failed to send chart. Please check your bot token and channel ID in the configuration."
    except Exception as e:
        logger.error(f"Error in send_latest_chart_to_discord_channel: {str(e)}")
        return "Unable to send chart. Please check your internet connection and try again."


@plugin.command("send_latest_shadowplay_clip_to_discord_channel")
def send_latest_shadowplay_clip_to_discord_channel(caption: str = ""):
    """
    Send latest ShadowPlay clip to Discord.
    
    Args:
        caption: Optional caption for the clip
    """
    global BOT_TOKEN, CHANNEL_ID, GAME_DIRECTORY, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not GAME_DIRECTORY:
        return "Game folder not configured. Please set `GAME_DIRECTORY` in your config file (e.g., \"Desktop\" or \"RUST\")."
    
    plugin.stream("Finding latest clip...")
    
    mp4_directory = os.path.join(BASE_MP4_DIRECTORY, GAME_DIRECTORY)
    file_path = find_latest_file(mp4_directory, ".mp4")
    
    if not file_path:
        return f"No video clip found for '{GAME_DIRECTORY}'. Make sure you have recorded a clip using NVIDIA ShadowPlay."
    
    plugin.stream("Uploading clip to Discord...")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            payload = {"content": caption}
            r = requests.post(url, headers=headers, data=payload, files=files, timeout=60)
        
        if r.status_code in [200, 201]:
            return "Clip sent successfully!"
        else:
            logger.error(f"Failed to send clip: {r.text}")
            return "Failed to send clip. The file may be too large for Discord (max 25MB) or check your configuration."
    except Exception as e:
        logger.error(f"Error in send_latest_shadowplay_clip_to_discord_channel: {str(e)}")
        return "Unable to send clip. Please check your internet connection and try again."


@plugin.command("send_latest_screenshot_to_discord_channel")
def send_latest_screenshot_to_discord_channel(caption: str = ""):
    """
    Send latest screenshot to Discord.
    
    Args:
        caption: Optional caption for the screenshot
    """
    global BOT_TOKEN, CHANNEL_ID, GAME_DIRECTORY, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not GAME_DIRECTORY:
        return "Game folder not configured. Please set `GAME_DIRECTORY` in your config file (e.g., \"Desktop\" or \"RUST\")."
    
    plugin.stream("Finding latest screenshot...")
    
    screenshot_directory = os.path.join(BASE_SCREENSHOT_DIRECTORY, GAME_DIRECTORY)
    file_path = find_latest_file(screenshot_directory, ".png")
    
    if not file_path:
        return f"No screenshot found for '{GAME_DIRECTORY}'. Make sure you have taken a screenshot using NVIDIA ShadowPlay."
    
    plugin.stream("Uploading screenshot to Discord...")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            payload = {"content": caption}
            r = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        
        if r.status_code in [200, 201]:
            return "Screenshot sent successfully!"
        else:
            logger.error(f"Failed to send screenshot: {r.text}")
            return "Failed to send screenshot. Please check your bot token and channel ID in the configuration."
    except Exception as e:
        logger.error(f"Error in send_latest_screenshot_to_discord_channel: {str(e)}")
        return "Unable to send screenshot. Please check your internet connection and try again."


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE
    
    load_config()
    if SETUP_COMPLETE:
        plugin.set_keep_session(False)
        return "Discord bot configured! You can now send messages, clips, and screenshots to your Discord channel."
    else:
        plugin.set_keep_session(True)
        return get_setup_instructions()


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Discord plugin (SDK version)...")
    load_config()
    plugin.run()

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
from typing import Any, Callable, Dict, Optional

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
PENDING_CALL: Optional[Dict[str, Any]] = None  # {"func": callable, "args": {...}}


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

Save the file and say **"next"** or **"continue"** when done, and I'll complete your original request.\r"""


def store_pending_call(func: Callable, **kwargs):
    """Store a function call to execute after setup completes."""
    global PENDING_CALL
    PENDING_CALL = {"func": func, "args": kwargs}
    logger.info(f"[SETUP] Stored pending call: {func.__name__}({kwargs})")


def execute_pending_call() -> Optional[str]:
    """Execute the stored pending call if one exists. Returns result or None."""
    global PENDING_CALL
    if not PENDING_CALL:
        return None
    
    func = PENDING_CALL["func"]
    args = PENDING_CALL["args"]
    PENDING_CALL = None  # Clear before executing
    
    logger.info(f"[SETUP] Executing pending call: {func.__name__}({args})")
    return func(_from_pending=True, **args)


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
def send_message_to_discord_channel(message: str = "", _from_pending: bool = False):
    """
    Send a text message to Discord channel.
    
    Args:
        message: The text message to send
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global BOT_TOKEN, CHANNEL_ID, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        store_pending_call(send_message_to_discord_channel, message=message)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not message:
        return (
            "**What should I send?**\n\n"
            "Please include a message to send to Discord."
        )
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream(f"_Sending message to Discord..._\n\n")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    payload = {"content": message}
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code in [200, 201]:
            logger.info("Message sent successfully.")
            return (
                "**Message sent!**\n\n"
                "Your message was delivered to the Discord channel."
            )
        elif r.status_code == 401:
            logger.error(f"Failed to send message (401): {r.text}")
            return (
                "**Authentication failed.**\n\n"
                "Your **Bot Token** appears to be invalid.\n\n"
                f"_Config:_ `{CONFIG_FILE}`"
            )
        elif r.status_code == 403:
            logger.error(f"Failed to send message (403): {r.text}")
            return (
                "**Permission denied.**\n\n"
                "The bot doesn't have permission to post in this channel.\n\n"
                "Check that your **Channel ID** is correct and the bot has been added to the server."
            )
        else:
            logger.error(f"Failed to send message ({r.status_code}): {r.text}")
            return (
                "**Failed to send message.**\n\n"
                f"Discord returned an error _(status {r.status_code})_.\n\n"
                "Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in send_message_to_discord_channel: {str(e)}")
        return (
            "**Connection error.**\n\n"
            "Unable to reach Discord. Please check your internet connection and try again."
        )


@plugin.command("send_latest_chart_to_discord_channel")
def send_latest_chart_to_discord_channel(caption: str = "", _from_pending: bool = False):
    """
    Send latest performance chart (CSV) to Discord.
    
    Args:
        caption: Optional caption for the file
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global BOT_TOKEN, CHANNEL_ID, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        store_pending_call(send_latest_chart_to_discord_channel, caption=caption)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream("_Finding latest performance chart..._\n\n")
    
    file_path = find_latest_file(CSV_DIRECTORY, ".csv")
    if not file_path:
        return (
            "**No performance chart found.**\n\n"
            "Charts are created when you record performance data in G-Assist.\n\n"
            f"_Expected location:_ `{CSV_DIRECTORY}`"
        )
    
    plugin.stream("_Uploading chart to Discord..._\n\n")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            payload = {"content": caption}
            r = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        
        if r.status_code in [200, 201]:
            return (
                "**Chart sent!**\n\n"
                "Your performance chart was uploaded to Discord."
            )
        elif r.status_code == 401:
            logger.error(f"Failed to send chart (401): {r.text}")
            return (
                "**Authentication failed.**\n\n"
                "Your **Bot Token** appears to be invalid.\n\n"
                f"_Config:_ `{CONFIG_FILE}`"
            )
        elif r.status_code == 403:
            logger.error(f"Failed to send chart (403): {r.text}")
            return (
                "**Permission denied.**\n\n"
                "The bot doesn't have permission to post in this channel.\n\n"
                "Check that your **Channel ID** is correct and the bot has been added to the server."
            )
        else:
            logger.error(f"Failed to send chart ({r.status_code}): {r.text}")
            return (
                "**Failed to send chart.**\n\n"
                f"Discord returned an error _(status {r.status_code})_.\n\n"
                "Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in send_latest_chart_to_discord_channel: {str(e)}")
        return (
            "**Connection error.**\n\n"
            "Unable to reach Discord. Please check your internet connection and try again."
        )


@plugin.command("send_latest_shadowplay_clip_to_discord_channel")
def send_latest_shadowplay_clip_to_discord_channel(caption: str = "", _from_pending: bool = False):
    """
    Send latest ShadowPlay clip to Discord.
    
    Args:
        caption: Optional caption for the clip
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global BOT_TOKEN, CHANNEL_ID, GAME_DIRECTORY, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        store_pending_call(send_latest_shadowplay_clip_to_discord_channel, caption=caption)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not GAME_DIRECTORY:
        return (
            "**Game folder not configured.**\n\n"
            "Please set `GAME_DIRECTORY` in your config file:\n"
            f"```\n{CONFIG_FILE}\n```\n\n"
            "Example values: `\"Desktop\"`, `\"RUST\"`, `\"Fortnite\"`"
        )
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream("_Finding latest ShadowPlay clip..._\n\n")
    
    mp4_directory = os.path.join(BASE_MP4_DIRECTORY, GAME_DIRECTORY)
    file_path = find_latest_file(mp4_directory, ".mp4")
    
    if not file_path:
        return (
            f"**No video clip found for '{GAME_DIRECTORY}'.**\n\n"
            "Make sure you have recorded a clip using **NVIDIA ShadowPlay**.\n\n"
            f"_Expected location:_ `{mp4_directory}`"
        )
    
    plugin.stream("_Uploading clip to Discord..._\n\n")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            payload = {"content": caption}
            r = requests.post(url, headers=headers, data=payload, files=files, timeout=60)
        
        if r.status_code in [200, 201]:
            return (
                "**Clip sent!**\n\n"
                "Your ShadowPlay clip was uploaded to Discord."
            )
        elif r.status_code == 401:
            logger.error(f"Failed to send clip (401): {r.text}")
            return (
                "**Authentication failed.**\n\n"
                "Your **Bot Token** appears to be invalid.\n\n"
                f"_Config:_ `{CONFIG_FILE}`"
            )
        elif r.status_code == 403:
            logger.error(f"Failed to send clip (403): {r.text}")
            return (
                "**Permission denied.**\n\n"
                "The bot doesn't have permission to post in this channel.\n\n"
                "Check that your **Channel ID** is correct and the bot has been added to the server."
            )
        elif r.status_code == 413 or (r.status_code == 400 and "size" in r.text.lower()):
            logger.error(f"Failed to send clip (file too large): {r.text}")
            return (
                "**File too large.**\n\n"
                "Discord has a **25MB** file size limit.\n\n"
                "Try recording a shorter clip or compressing the video."
            )
        else:
            logger.error(f"Failed to send clip ({r.status_code}): {r.text}")
            return (
                "**Failed to send clip.**\n\n"
                f"Discord returned an error _(status {r.status_code})_.\n\n"
                "Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in send_latest_shadowplay_clip_to_discord_channel: {str(e)}")
        return (
            "**Connection error.**\n\n"
            "Unable to reach Discord. Please check your internet connection and try again."
        )


@plugin.command("send_latest_screenshot_to_discord_channel")
def send_latest_screenshot_to_discord_channel(caption: str = "", _from_pending: bool = False):
    """
    Send latest screenshot to Discord.
    
    Args:
        caption: Optional caption for the screenshot
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global BOT_TOKEN, CHANNEL_ID, GAME_DIRECTORY, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        store_pending_call(send_latest_screenshot_to_discord_channel, caption=caption)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not GAME_DIRECTORY:
        return (
            "**Game folder not configured.**\n\n"
            "Please set `GAME_DIRECTORY` in your config file:\n"
            f"```\n{CONFIG_FILE}\n```\n\n"
            "Example values: `\"Desktop\"`, `\"RUST\"`, `\"Fortnite\"`"
        )
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream("_Finding latest screenshot..._\n\n")
    
    screenshot_directory = os.path.join(BASE_SCREENSHOT_DIRECTORY, GAME_DIRECTORY)
    file_path = find_latest_file(screenshot_directory, ".png")
    
    if not file_path:
        return (
            f"**No screenshot found for '{GAME_DIRECTORY}'.**\n\n"
            "Make sure you have taken a screenshot using **NVIDIA ShadowPlay**.\n\n"
            f"_Expected location:_ `{screenshot_directory}`"
        )
    
    plugin.stream("_Uploading screenshot to Discord..._\n\n")
    
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            payload = {"content": caption}
            r = requests.post(url, headers=headers, data=payload, files=files, timeout=30)
        
        if r.status_code in [200, 201]:
            return (
                "**Screenshot sent!**\n\n"
                "Your screenshot was uploaded to Discord."
            )
        elif r.status_code == 401:
            logger.error(f"Failed to send screenshot (401): {r.text}")
            return (
                "**Authentication failed.**\n\n"
                "Your **Bot Token** appears to be invalid.\n\n"
                f"_Config:_ `{CONFIG_FILE}`"
            )
        elif r.status_code == 403:
            logger.error(f"Failed to send screenshot (403): {r.text}")
            return (
                "**Permission denied.**\n\n"
                "The bot doesn't have permission to post in this channel.\n\n"
                "Check that your **Channel ID** is correct and the bot has been added to the server."
            )
        elif r.status_code == 413 or (r.status_code == 400 and "size" in r.text.lower()):
            logger.error(f"Failed to send screenshot (file too large): {r.text}")
            return (
                "**File too large.**\n\n"
                "Discord has a **25MB** file size limit.\n\n"
                "Try taking a screenshot at a lower resolution."
            )
        else:
            logger.error(f"Failed to send screenshot ({r.status_code}): {r.text}")
            return (
                "**Failed to send screenshot.**\n\n"
                f"Discord returned an error _(status {r.status_code})_.\n\n"
                "Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in send_latest_screenshot_to_discord_channel: {str(e)}")
        return (
            "**Connection error.**\n\n"
            "Unable to reach Discord. Please check your internet connection and try again."
        )


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE
    
    load_config()
    if SETUP_COMPLETE:
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Discord bot configured!_\n\n")
        result = execute_pending_call()
        if result is not None:
            plugin.set_keep_session(False)
            return result
        else:
            plugin.set_keep_session(False)
            return (
                "You're all set! You can now:\n\n"
                "- Send **messages** to your Discord channel\n"
                "- Share **ShadowPlay clips** and **screenshots**\n"
                "- Upload **performance charts**"
            )
    else:
        plugin.set_keep_session(True)
        return (
            "**Credentials not found.**\n\n"
            "The config file is still empty or invalid.\n\n"
            "---\n\n"
            "Please make sure you:\n"
            "1. Pasted your **Bot Token** and **Channel ID**\n"
            "2. **Saved** the file\n\n"
            f"_Config:_ `{CONFIG_FILE}`\n\n"
            "Say **\"next\"** or **\"continue\"** when ready."
        )


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Discord plugin (SDK version)...")
    load_config()
    plugin.run()

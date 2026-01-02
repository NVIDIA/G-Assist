"""
Twitch Plugin for G-Assist - V2 SDK Version

Check if Twitch users are live streaming.
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
import webbrowser
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
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Twitch API endpoints
TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAM_URL = "https://api.twitch.tv/helix/streams"

# ============================================================================
# GLOBAL STATE
# ============================================================================
oauth_token: Optional[str] = None
TWITCH_CLIENT_ID: Optional[str] = None
TWITCH_CLIENT_SECRET: Optional[str] = None
SETUP_COMPLETE = False
WIZARD_STEP = 0
PENDING_CALL: Optional[Dict[str, Any]] = None  # {"func": callable, "args": {...}}


def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    global TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, SETUP_COMPLETE
    
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            TWITCH_CLIENT_ID = config.get("TWITCH_CLIENT_ID", "")
            TWITCH_CLIENT_SECRET = config.get("TWITCH_CLIENT_SECRET", "")
            
            if TWITCH_CLIENT_ID and len(TWITCH_CLIENT_ID) > 20 and \
               TWITCH_CLIENT_SECRET and len(TWITCH_CLIENT_SECRET) > 20:
                SETUP_COMPLETE = True
                logger.info("Config loaded successfully")
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    return {}


def get_oauth_token() -> Optional[str]:
    """Obtain OAuth token from Twitch API."""
    global oauth_token
    
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    
    try:
        response = requests.post(
            TWITCH_OAUTH_URL,
            params={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials"
            },
            timeout=10
        )
        data = response.json()
        if "access_token" in data:
            oauth_token = data["access_token"]
            logger.info("Successfully obtained OAuth token")
            return oauth_token
        logger.error(f"Failed to get OAuth token: {data}")
        return None
    except Exception as e:
        logger.error(f"Error requesting OAuth token: {e}")
        return None


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


def get_setup_instructions_step1() -> str:
    """Return first step of setup wizard."""
    return """_
**Twitch Plugin - First Time Setup (1/2)**

Welcome! Let's set up your Twitch app. This takes about **5 minutes**.

---

**Create Your Twitch App**

I'm opening the Twitch Developer Console for you now...

1. Log in with your Twitch account
2. Click **Register Your Application**
3. Fill in the form:
   - Name: `G-Assist-Plugin`
   - OAuth Redirect URLs: `http://localhost:3000`
   - Category: **Application Integration**
4. Click **Create**

Say **"next"** or **"continue"** when you're ready for the next step.\r"""


def get_setup_instructions_step2() -> str:
    """Return second step of setup wizard."""
    return f"""_
**Twitch Plugin - First Time Setup (2/2)**

Great! Now let's add your credentials.

---

**Get Your Credentials**

1. Click **Manage** on your new app
2. Copy your **Client ID**
3. Click **New Secret** and copy it

_(Keep your client secret private!)_

---

**Add Them to the Config File**

I'm opening the config file for you:
```
{CONFIG_FILE}
```

Paste your credentials:
```
{{
  "TWITCH_CLIENT_ID": "YOUR_CLIENT_ID_HERE",
  "TWITCH_CLIENT_SECRET": "YOUR_CLIENT_SECRET_HERE"
}}
```

Say **"next"** or **"continue"** when you've saved the file, and I'll complete your original request.\r"""


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Check Twitch stream status"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("check_twitch_live_status")
def check_twitch_live_status(username: str = "", _from_pending: bool = False):
    """
    Check if a Twitch user is currently live.
    
    Args:
        username: Twitch username to check
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global oauth_token, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        global WIZARD_STEP
        WIZARD_STEP = 0  # Reset in case of re-setup
        store_pending_call(check_twitch_live_status, username=username)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        try:
            webbrowser.open("https://dev.twitch.tv/console/apps")
        except:
            pass
        return get_setup_instructions_step1()
    
    if not username:
        return "**Who should I check?** Please provide a Twitch username."
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream(f"_Checking if {username} is live_...\n\n")
    
    # Get OAuth token if needed
    if not oauth_token:
        oauth_token = get_oauth_token()
        if not oauth_token:
            plugin.set_keep_session(True)
            return (
                "**Authentication failed.** Your credentials may be invalid.\n\n"
                "Please check your `config.json` and try again."
            )
    
    try:
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {oauth_token}"
        }
        response = requests.get(
            TWITCH_STREAM_URL,
            headers=headers,
            params={"user_login": username},
            timeout=10
        )
        
        # Handle token expiration
        if response.status_code == 401:
            logger.info("OAuth token expired, refreshing...")
            oauth_token = get_oauth_token()
            if oauth_token:
                headers["Authorization"] = f"Bearer {oauth_token}"
                response = requests.get(
                    TWITCH_STREAM_URL,
                    headers=headers,
                    params={"user_login": username},
                    timeout=10
                )
        
        data = response.json()
        
        if "data" in data and data["data"]:
            stream_info = data["data"][0]
            # Strip non-ASCII for clean display
            title = ''.join(c for c in stream_info["title"] if ord(c) < 128)
            game = stream_info.get("game_name", "Unknown")
            game = ''.join(c for c in game if ord(c) < 128) if game else "Unknown"
            viewers = f"{stream_info['viewer_count']:,}"  # Format with commas
            
            return (
                f"**{username}** is **LIVE**!\n\n"
                f"**Title:** {title}\n"
                f"**Game:** {game}\n"
                f"**Viewers:** {viewers}\n"
                f"**Started:** {stream_info['started_at']}"
            )
        return f"**{username}** is currently **offline**. Check back later!"
        
    except Exception as e:
        logger.error(f"Error checking Twitch live status: {e}")
        return "**Error:** Failed to check Twitch live status. Please try again."


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE, WIZARD_STEP
    
    load_config()
    
    if SETUP_COMPLETE:
        # Verify with API
        token = get_oauth_token()
        if token:
            plugin.stream("_ ")  # Close engine's italic
            plugin.stream("_Twitch plugin configured!_\n\n")
            result = execute_pending_call()
            if result is not None:
                plugin.set_keep_session(False)
                return result
            else:
                plugin.set_keep_session(False)
                return ""
        else:
            plugin.set_keep_session(True)
            return (
                "**Verification failed.** Credentials found but couldn't authenticate.\n\n"
                "Please double-check your **Client ID** and **Client Secret** in the config file."
            )
    
    # Advance wizard
    if WIZARD_STEP == 0:
        WIZARD_STEP = 1
        plugin.set_keep_session(True)
        # Open config file
        try:
            if not os.path.exists(CONFIG_FILE):
                os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
                with open(CONFIG_FILE, "w") as f:
                    json.dump({"TWITCH_CLIENT_ID": "", "TWITCH_CLIENT_SECRET": ""}, f, indent=2)
            os.startfile(CONFIG_FILE)
        except:
            pass
        return get_setup_instructions_step2()
    else:
        # User says done but config not valid
        plugin.set_keep_session(True)
        return (
            "**Credentials not found.** The config file is still empty or invalid.\n\n"
            "Please make sure you:\n"
            "1. Pasted your **Client ID** and **Client Secret**\n"
            "2. **Saved** the file\n\n"
            "Then say **\"next\"** or **\"continue\"** to verify."
        )


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Twitch plugin (SDK version)...")
    load_config()
    plugin.run()

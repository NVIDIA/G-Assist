"""
IFTTT Plugin for G-Assist - V2 SDK Version

Triggers IFTTT webhooks with gaming news integration.
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
from typing import List, Optional

import feedparser
import requests

try:
    from gassist_sdk import Plugin
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
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
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================
IFTTT_WEBHOOK_KEY: Optional[str] = None
EVENT_NAME: Optional[str] = None
MAIN_RSS_URL = "https://feeds.feedburner.com/ign/pc-articles"
ALTERNATE_RSS_URL = "https://feeds.feedburner.com/ign/all"
SETUP_COMPLETE = False


def load_config():
    """Load webhook configuration."""
    global IFTTT_WEBHOOK_KEY, EVENT_NAME, MAIN_RSS_URL, ALTERNATE_RSS_URL, SETUP_COMPLETE
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        IFTTT_WEBHOOK_KEY = config.get("webhook_key", "")
        EVENT_NAME = config.get("event_name", "")
        MAIN_RSS_URL = config.get("main_rss_url", MAIN_RSS_URL)
        ALTERNATE_RSS_URL = config.get("alternate_rss_url", ALTERNATE_RSS_URL)
        
        if IFTTT_WEBHOOK_KEY and len(IFTTT_WEBHOOK_KEY) > 10 and EVENT_NAME:
            SETUP_COMPLETE = True
            logger.info(f"Successfully loaded config from {CONFIG_FILE}")
        else:
            logger.warning("Webhook key or event name is empty/invalid")
            IFTTT_WEBHOOK_KEY = None
            EVENT_NAME = None
    except FileNotFoundError:
        logger.error(f"Config file not found at {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error loading config: {e}")


def get_setup_instructions() -> str:
    """Return setup wizard instructions."""
    return f"""_
**IFTTT Plugin - First Time Setup**

Welcome! Let's set up your IFTTT webhook. This takes about **5 minutes**.

---

**Step 1: Create IFTTT Account**

1. Visit [IFTTT](https://ifttt.com/join)
2. Sign up for a free account

---

**Step 2: Get Webhook Key**

1. Visit [IFTTT Webhooks](https://ifttt.com/maker_webhooks)
2. Click **Documentation**
3. Your webhook key is shown at the top
4. Copy the key (it's after "/use/")

---

**Step 3: Create an Applet**

1. Visit [IFTTT Create](https://ifttt.com/create)
2. Click **+ If This** → search for **Webhooks** → select it
3. Choose **Receive a web request**
4. Enter an event name (e.g., "gaming_setup")
5. Click **+ Then That** → choose your action
6. Complete the applet setup

---

**Step 4: Configure the Plugin**

Open the config file at:
```
{CONFIG_FILE}
```

Update it with your values:
```
{{
  "webhook_key": "your_webhook_key_here",
  "event_name": "your_event_name_here",
  "main_rss_url": "https://feeds.feedburner.com/ign/pc-articles",
  "alternate_rss_url": "https://feeds.feedburner.com/ign/all"
}}
```

_(The plugin includes IGN gaming news headlines when triggering your applet!)_

Save the file and try the command again!\r"""


def fetch_ign_gaming_news() -> List[str]:
    """Fetch latest gaming news from IGN RSS feed."""
    try:
        logger.info("Fetching IGN gaming news")
        feed = feedparser.parse(MAIN_RSS_URL)
        
        if not feed.entries:
            logger.warning("No entries in main RSS feed, trying alternate")
            feed = feedparser.parse(ALTERNATE_RSS_URL)
        
        if feed.entries:
            headlines = [entry.title for entry in feed.entries[:3]]
            logger.info(f"Fetched {len(headlines)} headlines from IGN")
            return headlines
        else:
            logger.error("No entries found in either RSS feed")
            return []
    except Exception as e:
        logger.error(f"Error fetching IGN gaming news: {str(e)}")
        return []


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="IFTTT webhook trigger with gaming news"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("trigger_gaming_setup")
def trigger_gaming_setup():
    """
    Trigger IFTTT gaming setup applet with latest gaming news.
    """
    global IFTTT_WEBHOOK_KEY, EVENT_NAME, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not IFTTT_WEBHOOK_KEY or not EVENT_NAME:
        logger.info("[COMMAND] Webhook not configured - showing setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    plugin.stream("Fetching gaming news...")
    
    webhook_url = f"https://maker.ifttt.com/trigger/{EVENT_NAME}/with/key/{IFTTT_WEBHOOK_KEY}"
    webhook_data = {}
    
    # Fetch and include IGN news
    headlines = fetch_ign_gaming_news()
    if headlines:
        for i, headline in enumerate(headlines[:3], 1):
            webhook_data[f"value{i}"] = headline
        logger.info(f"Including {len(headlines)} news headlines in webhook")
    
    plugin.stream(f"Triggering IFTTT applet {EVENT_NAME}...")
    
    try:
        if webhook_data:
            response = requests.post(webhook_url, json=webhook_data, timeout=10)
        else:
            response = requests.post(webhook_url, timeout=10)
        
        if 200 <= response.status_code < 300:
            return f"IFTTT applet {EVENT_NAME} triggered successfully."
        else:
            logger.error(f"IFTTT webhook {EVENT_NAME} failed: {response.text}")
            return f"IFTTT applet {EVENT_NAME} failed: {response.text}"
    except Exception as e:
        logger.error(f"Error triggering IFTTT webhook {EVENT_NAME}: {str(e)}")
        return f"Error triggering IFTTT applet {EVENT_NAME}: {str(e)}"


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE
    
    load_config()
    if SETUP_COMPLETE:
        plugin.set_keep_session(False)
        return "IFTTT webhook configured! You can now trigger your gaming setup applet."
    else:
        plugin.set_keep_session(True)
        return get_setup_instructions()


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting IFTTT plugin (SDK version)...")
    load_config()
    plugin.run()

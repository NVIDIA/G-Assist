"""
Nanoleaf Plugin for G-Assist - V2 SDK Version

Control Nanoleaf light panels - colors and effects.
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
from typing import Any, Dict, Optional, Tuple

try:
    from gassist_sdk import Plugin
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

from nanoleafapi import Nanoleaf

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "nanoleaf"
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

# RGB Color values
RGB_VALUES = {
    "RED": (255, 0, 0), "GREEN": (0, 255, 0), "BLUE": (0, 0, 255),
    "CYAN": (0, 255, 255), "MAGENTA": (255, 0, 255), "YELLOW": (255, 255, 0),
    "BLACK": (0, 0, 0), "WHITE": (255, 255, 255), "GREY": (128, 128, 128),
    "GRAY": (128, 128, 128), "ORANGE": (255, 165, 0), "PURPLE": (128, 0, 128),
    "VIOLET": (128, 0, 128), "PINK": (255, 192, 203), "TEAL": (0, 128, 128),
    "BROWN": (165, 42, 42), "ICE_BLUE": (173, 216, 230), "CRIMSON": (220, 20, 60),
    "GOLD": (255, 215, 0), "NEON_GREEN": (57, 255, 20),
}

# ============================================================================
# GLOBAL STATE
# ============================================================================
NL: Optional[Nanoleaf] = None
NANOLEAF_IP: Optional[str] = None
SETUP_COMPLETE = False


def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    global NANOLEAF_IP, SETUP_COMPLETE
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            NANOLEAF_IP = config.get("ip", "")
            if NANOLEAF_IP and len(NANOLEAF_IP) > 5:
                SETUP_COMPLETE = True
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    return {"ip": ""}


def get_setup_instructions() -> str:
    """Return setup wizard instructions."""
    return f"""
NANOLEAF PLUGIN - FIRST TIME SETUP
===================================

Welcome! Let's set up your Nanoleaf. This takes about 2 minutes.

STEP 1 - Find Your Nanoleaf IP:
   1. Open the Nanoleaf app on your phone
   2. Go to Settings > Device Info
   3. Find the IP address (e.g., 192.168.1.100)

STEP 2 - Configure Plugin:
   1. Open this file: {CONFIG_FILE}
   2. Replace the empty IP with your Nanoleaf IP:
      {{"ip": "YOUR_NANOLEAF_IP_HERE"}}
   3. Save the file

STEP 3 - Authorize (first time only):
   1. Hold the power button on your Nanoleaf for 5-7 seconds
   2. The lights will flash, indicating pairing mode
   3. Send me ANY message to complete setup

After saving, send me ANY message (like "done") and I'll verify it!
"""


def get_rgb_code(color: str) -> Optional[Tuple[int, int, int]]:
    """Get RGB value for predefined color."""
    return RGB_VALUES.get(color.upper())


def ensure_connected() -> bool:
    """Ensure Nanoleaf connection is established."""
    global NL, NANOLEAF_IP
    if NL is not None:
        return True
    
    load_config()
    if not NANOLEAF_IP:
        return False
    
    try:
        NL = Nanoleaf(NANOLEAF_IP)
        logger.info(f"Successfully connected to Nanoleaf at {NANOLEAF_IP}")
        return True
    except Exception as e:
        logger.error(f"Error connecting to Nanoleaf: {str(e)}")
        NL = None
        return False


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Control Nanoleaf light panels"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("nanoleaf_change_room_lights")
def change_room_lights(color: str = ""):
    """
    Change Nanoleaf lights to a specific color.
    
    Args:
        color: Color name (RED, GREEN, BLUE, RAINBOW, OFF, BRIGHT_UP, BRIGHT_DOWN)
    """
    global NL, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not NANOLEAF_IP:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not ensure_connected():
        return f"Failed to connect to Nanoleaf at {NANOLEAF_IP}. Check the IP address."
    
    if not color:
        return "Missing color."
    
    color = color.upper()
    plugin.stream(f"Changing Nanoleaf lights to {color.lower()}...")
    
    # Special commands
    if color == "RAINBOW":
        try:
            effects = NL.list_effects()
            for effect in effects:
                if "northern" in effect.lower() or "aurora" in effect.lower():
                    NL.set_effect(effect)
                    return f"Set Nanoleaf to {effect} effect."
            # Fallback to first available effect
            if effects:
                NL.set_effect(effects[0])
                return f"Set Nanoleaf to {effects[0]} effect."
            return "No effects available."
        except Exception as e:
            return f"Failed to set effect: {str(e)}"
    
    if color == "OFF":
        try:
            NL.power_off()
            return "Nanoleaf powered off."
        except Exception as e:
            return f"Failed to power off: {str(e)}"
    
    if color == "BRIGHT_UP":
        try:
            NL.increment_brightness(10)
            return "Brightness increased."
        except Exception as e:
            return f"Failed to adjust brightness: {str(e)}"
    
    if color == "BRIGHT_DOWN":
        try:
            NL.increment_brightness(-10)
            return "Brightness decreased."
        except Exception as e:
            return f"Failed to adjust brightness: {str(e)}"
    
    # Regular color
    rgb_value = get_rgb_code(color)
    if not rgb_value:
        return f"Unknown color: {color}"
    
    try:
        NL.set_color(rgb_value)
        return "Nanoleaf lighting updated."
    except Exception as e:
        return f"Failed to set color: {str(e)}"


@plugin.command("nanoleaf_change_profile")
def change_profile(profile: str = ""):
    """
    Change Nanoleaf to a specific effect/profile.
    
    Args:
        profile: Name of the effect to apply
    """
    global NL, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not NANOLEAF_IP:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not ensure_connected():
        return f"Failed to connect to Nanoleaf at {NANOLEAF_IP}."
    
    if not profile:
        return "Missing profile name."
    
    plugin.stream(f"Changing Nanoleaf profile to {profile}...")
    
    try:
        effects = NL.list_effects()
        # Case-insensitive match
        effect_map = {e.upper(): e for e in effects}
        if profile.upper() in effect_map:
            NL.set_effect(effect_map[profile.upper()])
            return "Nanoleaf profile updated."
        else:
            return f"Unknown profile: {profile}. Available: {', '.join(effects[:5])}"
    except Exception as e:
        return f"Failed to set profile: {str(e)}"


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE
    
    load_config()
    if SETUP_COMPLETE and ensure_connected():
        plugin.set_keep_session(False)
        return "Nanoleaf configured! You can now control your lights."
    else:
        plugin.set_keep_session(True)
        return get_setup_instructions()


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Nanoleaf plugin (SDK version)...")
    load_config()
    plugin.run()

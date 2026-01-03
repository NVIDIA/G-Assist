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
from typing import Any, Callable, Dict, Optional, Tuple

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
PENDING_CALL: Optional[Dict[str, Any]] = None  # {"func": callable, "args": {...}}


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


def get_setup_instructions() -> str:
    """Return setup wizard instructions."""
    # Use forward slashes to prevent \n in path being interpreted as newline
    config_path = CONFIG_FILE.replace("\\", "/")
    return f"""_
**Nanoleaf Plugin - First Time Setup**

Welcome! Let's set up your Nanoleaf. This takes about **2 minutes**.

---

**Step 1: Find Your Nanoleaf IP**

1. Open your **Wi-Fi app** (Google Home, Eero, xFinity, etc.) or router admin page
2. Look for **Connected Devices**
3. Find your Nanoleaf and note its IP address (e.g., `192.168.1.100`)

---

**Step 2: Configure the Plugin**

Open the config file at:\r`{config_path}`\r
Add your Nanoleaf IP:
```
{{"ip": "YOUR_NANOLEAF_IP_HERE"}}
```

---

**Step 3: Authorize (First Time Only)**

1. Hold the power button on your Nanoleaf for **5-7 seconds**
2. The lights will flash, indicating pairing mode

Save the file and say **"next"** or **"continue"** when done, and I'll complete your original request.\r"""


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
def change_room_lights(color: str = "", _from_pending: bool = False):
    """
    Change Nanoleaf lights to a specific color.
    
    Args:
        color: Color name (RED, GREEN, BLUE, RAINBOW, OFF, BRIGHT_UP, BRIGHT_DOWN)
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global NL, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not NANOLEAF_IP:
        store_pending_call(change_room_lights, color=color)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not ensure_connected():
        return (
            "**Connection failed.**\n\n"
            f"Unable to connect to Nanoleaf at `{NANOLEAF_IP}`.\n\n"
            "Please check that:\n"
            "1. The **IP address** is correct\n"
            "2. Your Nanoleaf is **powered on** and connected to Wi-Fi\n"
            "3. You're on the **same network** as the device"
        )
    
    if not color:
        return (
            "**What color?**\n\n"
            "Please specify a color to set your Nanoleaf lights."
        )
    
    color = color.upper()
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream(f"_Changing Nanoleaf lights to {color.lower()}..._\n\n")
    
    # Special commands
    if color == "RAINBOW":
        try:
            effects = NL.list_effects()
            for effect in effects:
                if "northern" in effect.lower() or "aurora" in effect.lower():
                    NL.set_effect(effect)
                    return (
                        f"**Effect applied!**\n\n"
                        f"Nanoleaf is now displaying **{effect}**."
                    )
            # Fallback to first available effect
            if effects:
                NL.set_effect(effects[0])
                return (
                    f"**Effect applied!**\n\n"
                    f"Nanoleaf is now displaying **{effects[0]}**."
                )
            return (
                "**No effects available.**\n\n"
                "Your Nanoleaf doesn't have any saved effects.\n\n"
                "Try creating some in the Nanoleaf app first."
            )
        except Exception as e:
            logger.error(f"Failed to set rainbow effect: {str(e)}")
            return (
                "**Failed to set effect.**\n\n"
                "Unable to apply the rainbow effect. Please try again."
            )
    
    if color == "OFF":
        try:
            NL.power_off()
            return "**Nanoleaf powered off.**"
        except Exception as e:
            logger.error(f"Failed to power off: {str(e)}")
            return (
                "**Failed to power off.**\n\n"
                "Unable to turn off your Nanoleaf. Please try again."
            )
    
    if color == "BRIGHT_UP":
        try:
            NL.increment_brightness(10)
            return "**Brightness increased.**"
        except Exception as e:
            logger.error(f"Failed to adjust brightness: {str(e)}")
            return (
                "**Failed to adjust brightness.**\n\n"
                "Unable to increase brightness. Please try again."
            )
    
    if color == "BRIGHT_DOWN":
        try:
            NL.increment_brightness(-10)
            return "**Brightness decreased.**"
        except Exception as e:
            logger.error(f"Failed to adjust brightness: {str(e)}")
            return (
                "**Failed to adjust brightness.**\n\n"
                "Unable to decrease brightness. Please try again."
            )
    
    # Regular color
    rgb_value = get_rgb_code(color)
    if not rgb_value:
        available_colors = ", ".join(list(RGB_VALUES.keys())[:8])
        return (
            f"**Unknown color:** `{color}`\n\n"
            f"Try one of these: {available_colors}, ..."
        )
    
    try:
        NL.set_color(rgb_value)
        return (
            f"**Color updated!**\n\n"
            f"Nanoleaf is now set to **{color.lower()}**."
        )
    except Exception as e:
        logger.error(f"Failed to set color: {str(e)}")
        return (
            "**Failed to set color.**\n\n"
            "Unable to change the Nanoleaf color. Please try again."
        )


@plugin.command("nanoleaf_change_profile")
def change_profile(profile: str = "", _from_pending: bool = False):
    """
    Change Nanoleaf to a specific effect/profile.
    
    Args:
        profile: Name of the effect to apply
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global NL, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not NANOLEAF_IP:
        store_pending_call(change_profile, profile=profile)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not ensure_connected():
        return (
            "**Connection failed.**\n\n"
            f"Unable to connect to Nanoleaf at `{NANOLEAF_IP}`.\n\n"
            "Please check that:\n"
            "1. The **IP address** is correct\n"
            "2. Your Nanoleaf is **powered on** and connected to Wi-Fi\n"
            "3. You're on the **same network** as the device"
        )
    
    if not profile:
        return (
            "**Which profile?**\n\n"
            "Please specify the name of the effect or profile to apply."
        )
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream(f"_Changing Nanoleaf profile to {profile}..._\n\n")
    
    try:
        effects = NL.list_effects()
        # Case-insensitive match
        effect_map = {e.upper(): e for e in effects}
        if profile.upper() in effect_map:
            matched_effect = effect_map[profile.upper()]
            NL.set_effect(matched_effect)
            return (
                f"**Profile applied!**\n\n"
                f"Nanoleaf is now displaying **{matched_effect}**."
            )
        else:
            available = ", ".join(effects[:5])
            more = f" _(+{len(effects) - 5} more)_" if len(effects) > 5 else ""
            return (
                f"**Unknown profile:** `{profile}`\n\n"
                f"Available effects: {available}{more}"
            )
    except Exception as e:
        logger.error(f"Failed to set profile: {str(e)}")
        return (
            "**Failed to set profile.**\n\n"
            "Unable to apply the effect. Please try again."
        )


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE
    
    load_config()
    if SETUP_COMPLETE and ensure_connected():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Nanoleaf connected!_\n\n")
        result = execute_pending_call()
        if result is not None:
            plugin.set_keep_session(False)
            return result
        else:
            plugin.set_keep_session(False)
            return (
                "**Nanoleaf configured!**\n\n"
                "You're all set. You can now:\n\n"
                "- Change **light colors** on your Nanoleaf\n"
                "- Apply **effects and profiles**\n"
                "- Adjust **brightness**"
            )
    else:
        plugin.set_keep_session(True)
        # Use forward slashes to prevent \n in path being interpreted as newline
        config_path = CONFIG_FILE.replace("\\", "/")
        return (
            "**Configuration not found.**\n\n"
            "The config file is still empty or invalid.\n\n"
            "---\n\n"
            "Please make sure you:\n"
            "1. Added your **Nanoleaf IP address**\n"
            "2. **Saved** the file\n\n"
            f"_Config:_ `{config_path}`\n\n"
            "Say **\"next\"** or **\"continue\"** when ready."
        )


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Nanoleaf plugin (SDK version)...")
    load_config()
    plugin.run()

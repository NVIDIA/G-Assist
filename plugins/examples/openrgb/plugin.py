"""
OpenRGB Plugin for G-Assist - V2 SDK Version

Control RGB lighting via OpenRGB SDK server.
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
import logging
from typing import Optional

try:
    from gassist_sdk import Plugin
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "openrgb"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Color map
COLOR_MAP = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "yellow": (255, 255, 0), "purple": (128, 0, 128), "orange": (255, 165, 0),
    "pink": (255, 192, 203), "white": (255, 255, 255), "black": (0, 0, 0),
    "cyan": (0, 255, 255), "magenta": (255, 0, 255),
}

# ============================================================================
# GLOBAL STATE
# ============================================================================
CLI: Optional[OpenRGBClient] = None


def ensure_connected() -> bool:
    """Ensure OpenRGB connection is established."""
    global CLI
    if CLI is not None:
        return True
    
    try:
        CLI = OpenRGBClient("127.0.0.1", 6742, "G-Assist Plugin")
        logger.info("Successfully connected to OpenRGB service")
        return True
    except ConnectionRefusedError:
        logger.error("OpenRGB service is not running")
        return False
    except TimeoutError:
        logger.error("Timeout connecting to OpenRGB service")
        return False
    except Exception as e:
        logger.error(f"Error connecting to OpenRGB: {str(e)}")
        return False


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Control RGB lighting via OpenRGB"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("list_devices")
def list_devices():
    """List all available RGB devices."""
    if not ensure_connected():
        return (
            "OpenRGB service is not running. Please start OpenRGB and enable SDK server.\n"
            "Download from: https://openrgb.org/"
        )
    
    try:
        devices = [device.name for device in CLI.devices]
        if devices:
            return "Available devices:\n" + "\n".join(f"  - {d}" for d in devices)
        else:
            return "No RGB devices found."
    except Exception as e:
        return f"Failed to list devices: {e}"


@plugin.command("set_color")
def set_color(color_name: str = "", device_name: str = ""):
    """
    Set RGB color for device(s).
    
    Args:
        color_name: Color name (red, green, blue, yellow, etc.)
        device_name: Specific device or "all" for all devices
    """
    if not ensure_connected():
        return (
            "OpenRGB service is not running. Please start OpenRGB and enable SDK server.\n"
            "Download from: https://openrgb.org/"
        )
    
    if not color_name:
        return "Missing color_name."
    
    color_name = color_name.lower()
    if color_name not in COLOR_MAP:
        return f"Unknown color: {color_name}. Available: {', '.join(COLOR_MAP.keys())}"
    
    r, g, b = COLOR_MAP[color_name]
    color = RGBColor(r, g, b)
    
    if device_name and "all" not in device_name.lower():
        plugin.stream(f"Setting {device_name} to {color_name}...")
        try:
            devices = CLI.get_devices_by_name(device_name, False)
            if devices and len(devices) > 0:
                devices[0].set_color(color)
                return f"{device_name} set to {color_name}."
            else:
                return f"Device not found: {device_name}"
        except Exception as e:
            return f"Failed to set color: {e}"
    else:
        plugin.stream(f"Setting all devices to {color_name}...")
        try:
            all_devices = CLI.devices
            if not all_devices:
                return "No devices found."
            
            results = []
            for device in all_devices:
                device.set_color(color)
                results.append(f"{device.name} set to {color_name}")
            
            return "Updated devices:\n" + "\n".join(f"  - {r}" for r in results)
        except Exception as e:
            return f"Failed to set color: {e}"


@plugin.command("set_mode")
def set_mode(effect_name: str = "", device_name: str = ""):
    """
    Set RGB effect/mode for device(s).
    
    Args:
        effect_name: Effect mode name
        device_name: Specific device or "all" for all devices
    """
    if not ensure_connected():
        return (
            "OpenRGB service is not running. Please start OpenRGB and enable SDK server."
        )
    
    if not effect_name:
        return "Missing effect_name."
    
    if device_name and "all" not in device_name.lower():
        try:
            devices = CLI.get_devices_by_name(device_name, False)
            if devices and len(devices) > 0:
                device = devices[0]
                modes = {mode.name.lower(): mode for mode in device.modes}
                if effect_name.lower() in modes:
                    device.set_mode(effect_name)
                    return f"{device_name} set to {effect_name}."
                else:
                    return f"Effect not supported on {device_name}."
            else:
                return f"Device not found: {device_name}"
        except Exception as e:
            return f"Failed to set mode: {e}"
    else:
        try:
            all_devices = CLI.devices
            if not all_devices:
                return "No devices found."
            
            results = []
            for device in all_devices:
                modes = {mode.name.lower(): mode for mode in device.modes}
                if effect_name.lower() in modes:
                    device.set_mode(effect_name)
                    results.append(f"{device.name} set to {effect_name}")
                else:
                    results.append(f"{device.name} does not support {effect_name}")
            
            return "Results:\n" + "\n".join(f"  - {r}" for r in results)
        except Exception as e:
            return f"Failed to set mode: {e}"


@plugin.command("disable_lighting")
def disable_lighting():
    """Turn off all RGB lighting."""
    if not ensure_connected():
        return "OpenRGB service is not running."
    
    plugin.stream("Disabling RGB lighting...")
    
    try:
        for device in CLI.devices:
            device.set_mode("off")
        return "RGB lighting disabled."
    except Exception as e:
        return f"Failed to disable lighting: {e}"


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting OpenRGB plugin (SDK version)...")
    plugin.run()
